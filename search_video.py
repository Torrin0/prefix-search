import os
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np
import pandas as pd
from PIL import Image
from tqdm import tqdm
import torch
import open_clip
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

try:
    from transformers import ViTImageProcessor, ViTModel
    DINO_AVAILABLE = True
except ImportError:
    DINO_AVAILABLE = False

MOVIES_DIR = "movies"
OUT_DIR = "clips"
SAMPLE_FPS = 0.5
CLIP_SEC = 5.0
SMOOTH_SEC = 0.5
MIN_GAP_SEC = 3.0
TOP_PER_MOV = 80
BATCH = 16
MAX_WORKERS = 1

class DuoEncoder:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_clip, _, self.preprocess_clip = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
        self.model_clip.eval().to(self.device)
        self.tokenizer_clip = open_clip.get_tokenizer("ViT-B-32")
        if DINO_AVAILABLE:
            try:
                self.processor_dino = ViTImageProcessor.from_pretrained("facebook/dino-vitb16")
                self.model_dino = ViTModel.from_pretrained("facebook/dino-vitb16")
                self.model_dino.eval().to(self.device)
                self.dino_enabled = True
            except Exception:
                self.dino_enabled = False
        else:
            self.dino_enabled = False
        if self.device == "cpu":
            torch.set_num_threads(4)

    @torch.no_grad()
    def encode_text_clip(self, text: str) -> np.ndarray:
        tok = self.tokenizer_clip([text]).to(self.device)
        t = self.model_clip.encode_text(tok)
        t = t / t.norm(dim=-1, keepdim=True)
        return t.detach().cpu().numpy()[0].astype(np.float32)

    @torch.no_grad()
    def encode_images_clip(self, images: List[Image.Image]) -> np.ndarray:
        batch = torch.stack([self.preprocess_clip(im) for im in images]).to(self.device)
        x = self.model_clip.encode_image(batch)
        x = x / x.norm(dim=-1, keepdim=True)
        return x.detach().cpu().numpy().astype(np.float32)

    @torch.no_grad()
    def encode_images_dino(self, images: List[Image.Image]) -> np.ndarray:
        if not self.dino_enabled:
            return np.zeros((len(images), 768), dtype=np.float32)
        inputs = self.processor_dino(images=images, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        outputs = self.model_dino(**inputs)
        x = outputs.last_hidden_state[:, 0]
        x = x / (x.norm(dim=-1, keepdim=True) + 1e-6)
        return x.detach().cpu().numpy().astype(np.float32)

def bgr_to_pil(frame):
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

def iter_sampled_frames(video_path: str, sample_fps: float):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {video_path}")
    native = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(int(round(native / sample_fps)), 1)
    frame_idx = 0
    while True:
        ret = cap.grab()
        if not ret:
            break
        if frame_idx % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            ts = frame_idx / native
            yield frame, ts, frame_idx
        frame_idx += 1
    cap.release()

def optical_flow_motion(frames_bgr_window: List) -> float:
    """Р’С‹С‡РёСЃР»СЏРµС‚ РѕРїС‚РёС‡РµСЃРєРёР№ РїРѕС‚РѕРє - РїРѕРєР°Р·С‹РІР°РµС‚ РєСѓРґР° РґРІРёР¶СѓС‚СЃСЏ РїРёРєСЃРµР»Рё. Р­С‚Рѕ РЎРђРњР«Р™ РќРђР”Р•Р–РќР«Р™ СЃРїРѕСЃРѕР± РЅР°Р№С‚Рё Р°РєС‚РёРІРЅС‹Рµ СЃС†РµРЅС‹."""
    if len(frames_bgr_window) < 2:
        return 0.0
    flow_magnitudes = []
    for i in range(1, min(len(frames_bgr_window), 5)):
        prev_gray = cv2.cvtColor(frames_bgr_window[i-1], cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(frames_bgr_window[i], cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.resize(prev_gray, (160, 120))
        curr_gray = cv2.resize(curr_gray, (160, 120))
        try:
            flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            flow_magnitudes.append(np.mean(mag))
        except Exception:
            pass
    return float(np.mean(flow_magnitudes)) if flow_magnitudes else 0.0

def ffmpeg_cut(src: str, dst: str, start: float, duration: float):
    from shutil import which
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = which("ffmpeg") or "ffmpeg"
    back = 1.0
    rough = max(0.0, start - back)
    precise = start - rough
    cmd = [ffmpeg, "-hide_banner", "-ss", f"{rough:.3f}", "-i", src, "-ss", f"{precise:.3f}", "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-pix_fmt", "yuv420p", "-y", dst]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
    except Exception:
        pass

def smooth_1d(x: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return x
    ker = np.ones(k, dtype=np.float32) / k
    return np.convolve(x, ker, mode="same")

def cheap_metrics(frame_bgr):
    h, w = frame_bgr.shape[:2]
    if w == 0 or h == 0:
        return 0.0, 0.0
    new_h = int(h * (160 / max(w, 1)))
    small = cv2.resize(frame_bgr, (160, max(1, new_h)))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    nb_ratio = float((gray > 18).mean())
    edge_density = float(gray.std() / 255.0)
    return nb_ratio, edge_density

def process_single_movie(mpath: str, query: str, sample_fps: float, clip_sec: float, smooth_sec: float, min_gap_sec: float, top_per_movie: int, batch: int, class_dir: str):
    mname = os.path.basename(mpath)
    start_time = time.time()
    tqdm.write(f"Start: {mname}")
    enc = DuoEncoder()
    qvec = enc.encode_text_clip(query)
    tss, sims_clip, sims_optical, nb_list, ed_list = [], [], [], [], []
    frames_pil, frames_bgr = [], []
    total_frames = 0
    all_feats_clip = []
    
    for frame_bgr, ts, idx in iter_sampled_frames(mpath, sample_fps):
        frames_pil.append(bgr_to_pil(frame_bgr))
        frames_bgr.append(frame_bgr)
        nb, ed = cheap_metrics(frame_bgr)
        tss.append(ts)
        nb_list.append(nb)
        ed_list.append(ed)
        total_frames += 1
        
        if len(frames_pil) >= batch:
            elapsed = time.time() - start_time
            fps = total_frames / elapsed if elapsed > 0 else 0
            tqdm.write(f"Batch: {total_frames} | {fps:.1f} it/s")
            feats = enc.encode_images_clip(frames_pil)
            sims_clip.extend((feats @ qvec).tolist())
            sims_optical.extend([1.0] * len(frames_pil))
            all_feats_clip.append(feats)
            frames_pil.clear()
    
    if frames_pil:
        feats = enc.encode_images_clip(frames_pil)
        sims_clip.extend((feats @ qvec).tolist())
        sims_optical.extend([1.0] * len(frames_pil))
        all_feats_clip.append(feats)
    
    elapsed = time.time() - start_time
    fps = total_frames / elapsed if elapsed > 0 else 0
    tqdm.write(f"Done: {total_frames} | {fps:.1f} it/s")
    
    if not sims_clip:
        return [], []
    
    all_feats_clip = np.vstack(all_feats_clip)
    tss_np = np.array(tss, dtype=np.float32)
    sims_clip_np = np.array(sims_clip, dtype=np.float32)
    nb_np = np.array(nb_list, dtype=np.float32)
    ed_np = np.array(ed_list, dtype=np.float32)
    
    k = max(int(round(smooth_sec * sample_fps)), 1)
    sims_smooth = smooth_1d(sims_clip_np, k)
    
    thr = float(np.percentile(sims_smooth, 25))
    
    order = np.argsort(-sims_smooth)
    taken = np.zeros(len(sims_smooth), dtype=bool)
    min_gap = max(int(round(min_gap_sec * sample_fps)), 1)
    peaks = []
    
    for idx in order:
        if sims_smooth[idx] < thr or taken[idx]:
            continue
        l = max(0, idx - min_gap)
        r = min(len(sims_smooth), idx + min_gap + 1)
        taken[l:r] = True
        peaks.append(idx)
        if len(peaks) >= top_per_movie:
            break
    
    half_w = int(round((clip_sec / 2.0) * sample_fps))
    final_peaks = []
    
    for pi in peaks:
        l = max(0, pi - half_w)
        r = min(len(frames_bgr), pi + half_w + 1)
        window = frames_bgr[l:r]
        
        nb_win = float(np.mean(nb_np[l:r]))
        ed_win = float(np.mean(ed_np[l:r]))
        
        if nb_win < 0.05 or ed_win < 0.003:
            continue
        
        optical_flow_score = optical_flow_motion(window)
        
        if optical_flow_score < 2.0:
            continue
        
        if len(window) >= 3:
            win_feats = all_feats_clip[l:r]
            if win_feats.shape[0] >= 2:
                sims_mat = np.dot(win_feats, win_feats.T)
                idx_triu = np.triu_indices(len(win_feats), k=1)
                if idx_triu[0].size > 0:
                    diversity = 1.0 - np.mean(sims_mat[idx_triu])
                    if diversity < 0.05:
                        continue
        
        final_peaks.append(pi)
    
    final_peaks.sort(key=lambda i: -sims_smooth[i])
    
    cut_tasks = []
    csv_rows = []
    for i, pi in enumerate(final_peaks[:30], 1):
        t_center = float(tss_np[pi])
        start = max(0.0, t_center - clip_sec / 2)
        out_name = f"{Path(mpath).stem}_{int(start)}_{int(start+clip_sec)}_{query}_{i:03d}.mp4"
        out_path = str(Path(class_dir) / out_name)
        cut_tasks.append((mpath, out_path, start, clip_sec))
        csv_rows.append({"outfile": out_path, "start_sec": float(start), "end_sec": float(start+clip_sec), "query": query})
    
    dur = time.time() - start_time
    tqdm.write(f"READY: {len(cut_tasks)} clips | {dur:.1f}s")
    return cut_tasks, csv_rows

def cut_clips_parallel(tasks, max_workers=MAX_WORKERS):
    if not tasks:
        return []
    def _cut(task):
        try:
            ffmpeg_cut(*task)
            return True
        except Exception:
            return False
    print(f"Cutting {len(tasks)} clips...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(tqdm(executor.map(_cut, tasks), total=len(tasks), desc="Cutting"))
    print(f"Done: {sum(results)}/{len(results)}")

def search_once_parallel(query: str):
    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    class_dir = Path(OUT_DIR) / query
    class_dir.mkdir(parents=True, exist_ok=True)
    
    movie_paths = sorted([p for ext in ("*.mp4", "*.mkv", "*.avi", "*.mov") for p in Path(MOVIES_DIR).rglob(ext)])
    if not movie_paths:
        print(f"No movies in {MOVIES_DIR}")
        return
    
    all_cut_tasks = []
    all_csv_rows = []
    print(f"Processing {len(movie_paths)} movies...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_movie, str(mp), query, SAMPLE_FPS, CLIP_SEC, SMOOTH_SEC, MIN_GAP_SEC, TOP_PER_MOV, BATCH, str(class_dir)): mp for mp in movie_paths}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Movies"):
            try:
                cut_tasks, csv_rows = future.result()
                all_cut_tasks.extend(cut_tasks)
                all_csv_rows.extend(csv_rows)
            except Exception as e:
                tqdm.write(f"Error: {e}")
    
    if all_cut_tasks:
        cut_clips_parallel(all_cut_tasks)
    
    df = pd.DataFrame(all_csv_rows, columns=["outfile", "start_sec", "end_sec", "query"])
    csv_path = Path(OUT_DIR) / f"results_{query}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"Saved: {csv_path} | Clips: {len(df)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python search_video.py "<query>"')
        sys.exit(0)
    search_once_parallel(sys.argv[1])