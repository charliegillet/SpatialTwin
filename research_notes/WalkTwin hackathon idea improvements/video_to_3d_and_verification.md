# Phone video to a measured indoor model, and a verifiable render-vs-video loop (WalkTwin)

Scope: tools usable in one day on Apple Silicon MacBooks, in a public open-source repo, to (a) get camera poses and metric scale from phone video, (b) replace the model-reported loop score with a deterministic measured metric, (c) make the live demo more striking without overstating anything. Research date: 25 Oct 2026. License facts were read from the GitHub API, LICENSE files and Hugging Face model tags on that date.

---

## Q1. Camera poses and metric scale from monocular phone video (COLMAP/GLOMAP, DUSt3R/MASt3R, VGGT, CUT3R, MegaSaM, Depth Anything, Depth Pro, MapAnything, MoGe, WebXR/ARKit)

### Takeaway
A license-clean, Mac-friendly stack exists: **pycolmap 4.2 (BSD, arm64 wheels, GLOMAP global mapper built in)** for poses, plus scale from the tape-measured anchor, cross-checked by a permissively licensed metric model (**MapAnything-apache**, **Depth Anything 3 METRIC-LARGE / BASE / SMALL (Apache-2.0)**, or **MoGe-2 (MIT)**). Most of the famous feed-forward models are non-commercial: DUSt3R, MASt3R, MASt3R-SLAM, CUT3R, the original VGGT-1B, Pi3/Pi3X weights, UniDepth, Depth Pro, and the larger Depth Anything V2 and DA3 models. Phone-browser pose capture works only on Android Chrome (WebXR + ARCore). iPhone Safari has no WebXR AR.

### Cited Findings
**Classical SfM**
- COLMAP is BSD ("new BSD license") — [COLMAP LICENSE](https://github.com/colmap/colmap/blob/main/LICENSE). GLOMAP is BSD-3-Clause — [colmap/glomap](https://github.com/colmap/glomap).
- GLOMAP's global SfM pipeline became part of COLMAP 4.0.0 (changelog dated 14 Mar 2026), run via `global_mapper` or `automatic_reconstructor --mapper GLOBAL`. It is now maintained in the COLMAP repo — [COLMAP 4.0 coverage](https://radiancefields.com/colmap-4.0-introduces-major-performance-and-infrastructure-updates); [COLMAP 4.1 changelog mirror](https://codegraph.jelmer.uk/colmap/4.1.0-2/CHANGELOG.rst).
- GLOMAP claims to be "typically 1-2 orders of magnitude faster" than incremental COLMAP, with on-par or better quality (the project's own claim) — [colmap/glomap](https://github.com/colmap/glomap).
- COLMAP 4.2.0 added `GlobalMapper.multiple_models` (on by default), which keeps disconnected components as separate models instead of discarding them — [COLMAP 4.2.0 coverage](https://radiancefields.com/colmap-4.2.0-adds-multi-component-global-mapping-and-loma-learned-matching).
- `pycolmap` 4.2.1 on PyPI is BSD-3-Clause and ships `macosx_14_0_arm64` wheels for CPython 3.10–3.13, so `pip install pycolmap` works on Apple Silicon with no build — [PyPI pycolmap](https://pypi.org/project/pycolmap/) (checked through the PyPI JSON API).

**Feed-forward multi-view models**
- **VGGT:** the code moved to "VGGT License v1" (29 Jul 2025), which permits commercial use except military. Only the **VGGT-1B-Commercial** checkpoint may be used commercially, and it sits behind an application form. The original VGGT-1B checkpoint stays non-commercial (HF tag `cc-by-nc-4.0`) — [VGGT README](https://github.com/facebookresearch/vggt); [HF VGGT-1B-Commercial](https://huggingface.co/facebook/VGGT-1B-Commercial) (HF API: `license:other`, `gated: manual`).
- VGGT "typically reconstructs a scene in less than 1 second" (GPU). It exports COLMAP format with optional bundle adjustment (`demo_colmap.py --use_ba`), and the README says the export feeds gsplat directly — [VGGT README](https://github.com/facebookresearch/vggt). The commercial checkpoint scores AUC@30 90.37 against 89.98 for the original on Co3D — same source.
- **MapAnything (Meta, 3DV 2026):** a feed-forward *metric* reconstruction model. Its outputs include camera poses, intrinsics, depth and a `metric_scaling_factor`. Weights come in `facebook/map-anything` (CC-BY-NC 4.0) and **`facebook/map-anything-apache` (Apache 2.0)**. The repo is Apache-2.0, has a commit adding MPS inference support (device auto-select CUDA > MPS > CPU), a `demo_colmap.py` export, and a Gradio app that accepts video — [MapAnything GitHub](https://github.com/facebookresearch/map-anything).
- MapAnything accuracy (paper v1). Multi-view dense reconstruction from images only, 50 views, averaged over ETH3D, ScanNet++ v2 and TartanAirV2: metric-scale relative error **0.16** (about 16%). Two views, images only: pose ATE 0.03 against VGGT's 0.07, and depth rel 0.08 against VGGT's 0.13. Multi-view metric depth on ScanNet (Robust-MVD) is reported as rel 32.26, worse than MUSt3R's 7.66 — [MapAnything arXiv 2509.13414](https://arxiv.org/html/2509.13414v1). (The paper's claim that it "outperforms" MUSt3R doesn't match that ScanNet number. Note the inconsistency.)
- **Depth Anything 3 (ByteDance, Nov 2025):** the DA3 main series estimates camera extrinsics and intrinsics from one or more images. **DA3-BASE (0.12B) and DA3-SMALL (0.08B) are Apache 2.0**, while DA3-LARGE and DA3-GIANT are CC BY-NC 4.0. **DA3METRIC-LARGE is Apache 2.0** and gives metric depth via `metric_depth = focal * net_output / 300`. The nested metric model (DA3NESTED-GIANT-LARGE) is CC BY-NC 4.0. Exports include glb, ply, npz and COLMAP-style extrinsics. DA3-Streaming handles long video in under 12 GB GPU memory — [DA3 GitHub](https://github.com/bytedance-seed/depth-anything-3); HF API tags confirmed: [DA3-BASE](https://huggingface.co/depth-anything/DA3-BASE), [DA3METRIC-LARGE](https://huggingface.co/depth-anything/DA3METRIC-LARGE).
- **Pi3 / Pi3X:** code BSD-3-Clause. The README says the "Model Weights (Pi3 and Pi3X Weights)" are CC BY-NC 4.0, strictly non-commercial. Pi3X adds approximate metric scale and pose/intrinsics conditioning — [Pi3 README](https://github.com/yyfz/Pi3). Conflict: the HF tag on `yyfz233/Pi3` says `bsd-2-clause`, but the README is explicit, so treat the weights as non-commercial.
- **DUSt3R / MASt3R:** CC BY-NC-SA 4.0 (Naver), "non-commercial use only". The checkpoints also inherit non-commercial dataset terms — [DUSt3R LICENSE copy](https://huggingface.co/spaces/tencent/Hunyuan3D-1/blob/c8486ac1e755d6fe9f58211154ef050f712b6020/third_party/dust3r/LICENSE); [MASt3R CHECKPOINTS_NOTICE mirror](https://huggingface.co/spaces/zino36/Demo/raw/35504b0728173d5d50d636d45441e3ad1aa58dc0/CHECKPOINTS_NOTICE).
- **MASt3R-SLAM:** CC BY-NC-SA 4.0 — [MASt3R-SLAM LICENSE](https://github.com/rmurai0610/MASt3R-SLAM).
- **CUT3R (CVPR 2025 oral, streaming):** CC BY-NC-SA 4.0 — [CUT3R LICENSE](https://github.com/CUT3R/CUT3R).
- **MegaSaM (CVPR 2025):** the repo is Apache-2.0 per the GitHub API. It targets camera and depth from casual dynamic monocular video — [mega-sam GitHub](https://github.com/mega-sam/mega-sam); [project page](https://mega-sam.github.io/).

**Monocular metric depth (scale cross-check)**
- **Apple Depth Pro:** the HF weights moved to the `apple-amlr` license (Feb 2025), which grants use "exclusively for Research Purposes" and excludes commercial products — [HF apple/DepthPro LICENSE](https://huggingface.co/apple/DepthPro/blob/main/LICENSE). **Not usable here.**
- **Depth Anything V2:** "Depth-Anything-V2-Small model is under the Apache-2.0 license. Depth-Anything-V2-Base/Large/Giant models are under the CC-BY-NC-4.0 license." The metric-depth fine-tunes (Hypersim indoor, Virtual KITTI outdoor) come in Small, Base and Large, with `max_depth = 20` m for indoor — [DA-V2 README](https://github.com/DepthAnything/Depth-Anything-V2); [metric_depth README](https://github.com/DepthAnything/Depth-Anything-V2/tree/main/metric_depth).
- **MoGe-2 (Microsoft):** gives a metric point map, metric depth, normals and camera FOV from one image. Code is MIT (DINOv2 parts Apache-2.0). HF tags on `Ruicheng/moge-2-vitl-normal` and `vits-normal` are `mit` — [MoGe README](https://github.com/microsoft/MoGe).
- **UniDepth:** CC BY-NC 4.0 — [UniDepth LICENSE](https://github.com/lpiccinelli-eth/UniDepth).
- **Metric3D (v2):** BSD-2-Clause code — [Metric3D GitHub](https://github.com/YvanYin/Metric3D). (Weight license not separately checked.)

**Phone capture of poses (no special hardware)**
- Safari does not support WebXR AR on iPhone, iPad or Vision Pro. visionOS Safari supports immersive VR only — [WWDC24 WebXR session](https://developer.apple.com/videos/play/wwdc2024/10066/); [LinkedIn article, weaker source](https://www.linkedin.com/pulse/webxr-still-broken-iphones-clyde-desouza-ja4zf); [iQ3Connect](https://iq3connect.com/webxr-on-ios-how-iq3connect-brings-web-based-augmented-reality-to-ipads-and-iphones/).
- **Android Chrome:** the WebXR Raw Camera Access module gives "pose-synchronized camera image textures" in `immersive-ar` sessions (`requiredFeatures: ["camera-access"]`, read through WebGL). It is implemented on ARCore and available only on Android — [Intent to Ship](https://groups.google.com/a/chromium.org/g/blink-dev/c/LoCH4tthbsI); [W3C module](https://immersive-web.github.io/raw-camera-access/); [caniuse](https://caniuse.com/wf-webxr-camera). The interface is `[SecureContext]`, so the page must be served over HTTPS — [W3C module IDL](https://immersive-web.github.io/raw-camera-access/).
- **iPhone native options:** Stray Scanner is an open-source app that records RGB, LiDAR depth, per-frame camera pose estimates, intrinsics and IMU, but it **needs a LiDAR device** — [App Store](https://apps.apple.com/us/app/id1557051662). NeRFCapture (MIT) streams ARKit-posed images and adds depth when LiDAR is present — [search summary of jc211's GitHub](https://github.com/jc211).
- **Apple RoomPlan** relies on camera plus LiDAR and returns walls, doors, windows and openings in metres, with USDZ and CapturedRoom JSON export. Capture calls are ignored on Mac Catalyst — [Apple RoomPlan docs](https://developer.apple.com/documentation/roomplan.md); [third-party Flutter plugin docs](https://pub.dev/documentation/roomplan/latest/) (secondary).

**Apple Silicon**
- No VGGT-specific MPS reports turned up. A macOS 26 Apple Developer Forums thread reports an MPS SDPA attention regression on M1 that doesn't affect M2 and later (that report concerns Core ML) — [Apple Dev Forums 820097](https://developer.apple.com/forums/thread/820097).

### Inferences
- **Recommended pose pipeline (about 2–3 h to wire):**
  1. `ffmpeg` samples 2 fps from the prepared 720p mp4, giving 90–300 frames for a 45–150 s walk.
  2. `pycolmap` extracts SIFT features, uses sequential matching (it's video) and runs `global_mapper`.
  3. Output: camera poses and a sparse point cloud *up to scale*.

  CPU-only SIFT on a few hundred 720p frames should take minutes on an M-series laptop (my estimate, not measured; benchmark it at kickoff). If SfM fails on blank walls, fall back to MapAnything-apache or DA3-BASE (Apache) on MPS. Both export COLMAP format, so downstream code doesn't change.
- **Monocular SfM never gives metric scale by itself.** Use three independent scale sources and show their agreement:
  - **(i) Tape-measured anchor door:** click the two jambs in 2+ frames and triangulate with the SfM poses.
  - **(ii) Camera height above the RANSAC floor plane** against a declared eye height of 1.5 ± 0.1 m (label it "declared").
  - **(iii) Median ratio of MoGe-2 or DA3METRIC metric depth to SfM depth** at sparse points (MIT / Apache).

  A "scale agreement" badge (for example "anchor 1.00, metric-depth 0.94, eye-height 1.03") is honest and visible. Use (i) as the authority and (ii) and (iii) as cross-checks.
- Expect metric models alone to be off by roughly 10–20% in scale indoors, based on MapAnything's 0.16 average relative scale error. That is too coarse to decide an 813 mm ADA door threshold. The tape anchor remains essential, and the plan's "cannot measure when band straddles" logic is right.
- The VGGT-1B-Commercial gate (manual approval) is a schedule risk on the day. Prefer MapAnything-apache or DA3-BASE if a feed-forward model is wanted.
- **Android-only WebXR capture is a stretch goal.** It gives metric ARCore VIO poses per frame, which removes the scale problem. But it needs HTTPS on the LAN (self-signed cert or tunnel), an ARCore-capable Android phone, and a custom recorder page. It is not worth it unless a teammate already has Android plus WebXR experience. Don't depend on iPhone for this.

### Gaps
- No measured runtime for VGGT, MapAnything or DA3 on MPS was found. MapAnything has an MPS commit but no published Mac benchmarks.
- MegaSaM's repo is Apache-2.0, but I did not verify the licenses of the depth-prior weights it downloads (it reportedly uses other monocular depth models). Verify before use.
- The license of the Depth Anything V2 *metric* checkpoints is not tagged on HF. By the main README they likely follow their base model (Small Apache, others NC), but this is unconfirmed.
- No published numeric accuracy for COLMAP/GLOMAP scale on phone walkthroughs (scale is undefined without an anchor). I found no Apple-published RoomPlan accuracy tolerance.

---

## Q2. Floor-plan and layout extraction to cross-check Argon's graph (SceneScript, SpatialLM, RoomFormer, HorizonNet, RoomPlan)

### Takeaway
None of the learned layout models is both permissively licensed and Mac-runnable in a day. SpatialLM's point-cloud encoders and SceneScript are CC BY-NC, SpatialLM needs CUDA 12.4, its suggested video-to-point-cloud step (MASt3R-SLAM) is CC BY-NC-SA, and HorizonNet needs a 360° panorama. The practical cross-check is a **deterministic geometric layout from the SfM point cloud**: floor plane, 2D density map, Manhattan wall lines. It is independent of Argon, fast, and fully open.

### Cited Findings
- **SpatialLM (NeurIPS 2025)** takes a point cloud with the prompt "Detect walls, doors, windows, boxes" and outputs a structured layout — [arXiv 2506.07491](https://arxiv.org/html/2506.07491v1).
- SpatialLM licensing: the Qwen variants derive from Qwen-2.5 (Apache-2.0) and the Llama variants from Llama 3.2 (Llama 3.2 license). But the **SpatialLM 1.0 (SceneScript encoder) and 1.1 (Sonata encoder) point-cloud encoder weights are CC-BY-NC-4.0**. The repo's root LICENSE is the Llama 3.2 Community License. Tested on CUDA 12.4 with TorchSparse; no Mac support is mentioned. Monocular video goes through MASt3R-SLAM or SLAM3R to get a point cloud — [SpatialLM GitHub](https://github.com/manycore-research/SpatialLM); HF tag on SpatialLM1.1-Qwen-0.5B is `cc-by-nc-4.0`.
- SpatialLM reported layout F1 on Structured3D (@0.25 / @0.5 IoU): RoomFormer 83.4 / 81.4, SceneScript (fine-tuned) 90.4 / 89.2, SpatialLM1.1-Qwen-0.5B (fine-tuned) 94.3 / 93.5. Zero-shot on videos, wall F1 @0.25 IoU is about 68–69 — [SpatialLM GitHub](https://github.com/manycore-research/SpatialLM).
- MASt3R-SLAM is CC BY-NC-SA 4.0 — [LICENSE](https://github.com/rmurai0610/MASt3R-SLAM).
- **SceneScript (Meta):** CC BY-NC 4.0 (Attribution-NonCommercial 4.0 International) — [scenescript LICENSE](https://github.com/facebookresearch/scenescript).
- **RoomFormer:** MIT — [ywyue/RoomFormer](https://github.com/ywyue/RoomFormer). **HorizonNet:** MIT — [sunset1995/HorizonNet](https://github.com/sunset1995/HorizonNet).
- **RoomPlan** needs LiDAR and returns doors, windows and openings in metres; Mac Catalyst cannot capture — [Apple RoomPlan docs](https://developer.apple.com/documentation/roomplan.md).

### Inferences
- **Recommended deterministic cross-check ("Geometry says"):**
  1. Fit the floor plane in the SfM cloud with RANSAC and set gravity.
  2. Project points between 0.3 and 2.2 m height into a 5 cm 2D histogram.
  3. Find the dominant orientation (Manhattan), then extract axis-aligned wall lines with a Hough transform on the density image.
  4. Compare with Argon's zone rects: wall-line distance and room-extent IoU.
  5. Door candidates are gaps along a wall line where the camera trajectory crosses it. The walker physically passed through, which is strong, independent door evidence.

  "Trajectory crosses wall line ⇒ there must be a door/opening here" is a striking and honest check of Argon's door list (it catches missed doors). It costs about 100–200 lines of numpy/OpenCV.
- RoomFormer (MIT) consumes exactly such a density map, but its CUDA deformable-attention ops and Structured3D training make a Mac run within a day risky. Treat it as optional.
- RoomPlan is a good *ground-truth* tool if a teammate owns a LiDAR iPhone Pro: scan the venue once to make an answer key, alongside the tape measurements. It is not part of the judge's path.

### Gaps
- Whether RoomFormer's custom ops build on macOS/MPS was not checked.
- No source quantifies how well Hough or Manhattan wall extraction from *sparse* SfM clouds of low-texture interiors works. Dense MVS (COLMAP `patch_match_stereo`) is CUDA-only in COLMAP, as far as I know; not verified here.

---

## Q3. Deterministic loop metrics: reprojection, edge or line alignment, segmentation IoU, depth agreement, SSIM/LPIPS

### Takeaway
Use metrics computed from geometry recovered *without Argon* (SfM poses and points, image edges, metric depth), never from Argon's own judgment. The most robust and simple headline is a **3D point-to-wall agreement score** (share of SfM points explained by the twin's walls and floor, plus share of the camera path that crosses walls only at doors). Supplement it with a **2D edge-chamfer score** on held-out frames. Plain SSIM/LPIPS between untextured renders and photos mostly measures appearance, not geometry.

### Cited Findings
- Edge-based chamfer matching with a distance transform is an established way to register *textureless* CAD models to images. D2CO (Imperoli & Pretto 2015) handles partial occlusion and avoids ICP's re-association step — [D2CO record](https://www.diag.uniroma1.it/node/17388); [iris.uniroma1.it](https://iris.uniroma1.it/handle/11573/804290).
- Render-and-compare refinement converges in a few iterations. SPARC converges in about 3 iterations and raised ScanNet CAD alignment accuracy from 25.0% to 31.8% — [SPARC](https://deepai.org/publication/sparc-sparse-render-and-compare-for-cad-model-alignment-in-a-single-rgb-image). HOC-Search found depth-plus-mask render-and-compare beat chamfer as an objective, and chamfer was slower — [HOC-Search](https://ar5iv.labs.arxiv.org/html/2309.06107).
- OpenCV's LSD line detector was removed in 3.4.6–3.4.15 and 4.1.0–4.5.3 over a license conflict, then restored once the NFA code was published under MIT. It is present in current 4.x docs (4.12, 4.13) — [OpenCV LSD docs](https://docs.opencv.org/4.x/db/d73/classcv_1_1LineSegmentDetector.html); [OpenCV 4.13 javadoc](https://docs.opencv.org/4.13.0/javadoc/org/opencv/imgproc/LineSegmentDetector.html). DeepLSD (learned) is MIT — [cvg/DeepLSD](https://github.com/cvg/DeepLSD).
- SAM 2 weights are Apache-2.0 (HF `facebook/sam2.1-hiera-large`). The README install says it "requires compiling a custom CUDA kernel with the nvcc compiler" and needs torch ≥ 2.5.1 — [SAM 2 README](https://github.com/facebookresearch/sam2). SAM 3 uses a custom "SAM License" (19 Nov 2025) — [sam3 LICENSE](https://github.com/facebookresearch/sam3).
- Pose-and-reconstruction benchmarks use AUC for pose, F1/Chamfer for geometry and PSNR/SSIM/LPIPS only for *novel-view rendering quality* of photoreal outputs — [DA3 README benchmark section](https://github.com/bytedance-seed/depth-anything-3).

### Inferences
**Freeze the registration first (the anti-gaming rule).** After iteration 0, compute one similarity transform from the SfM frame to the graph frame: gravity from the floor plane, scale from the tape anchor, and yaw/translation from a one-time fit. Store its hash with the run. If the transform were re-fit each iteration, score gains could come from re-alignment rather than graph fixes.

**Metric A, the headline "Geometry agreement" (3D, deterministic, cheap).** For SfM points at wall height (0.3–2.2 m above the floor):
- **Wall support:** the share within 0.15 m of a modeled wall segment.
- **Unexplained points:** the share outside all zone rects (missed area or a wrong rect).
- **Trajectory consistency:** the share of camera-path crossings of modeled walls that occur within 0.5 m of a modeled door. The walker cannot pass through a wall, so every crossing away from a door is a provable error with a timestamp.
- **Combined score:** for example the F1 of wall support and point coverage, and/or "N illegal wall crossings".

These are integers and fractions anyone can recompute, and "illegal crossings 3 → 0" is a very legible way to show the score climbing.

**Metric B, "Edge alignment" (2D, per frame, held-out).**
1. Project the twin's floor-wall lines, vertical corners and door jambs into frames using the *SfM* poses.
2. Run Canny or LSD on the real frame and build a distance transform.
3. Score the mean truncated distance in px (cap at about 20 px) and the edge inlier ratio (share of projected edge length within 5 px).
4. Report it on **held-out frames Argon never saw in the critique**, like a train/test split. This is the strongest answer to "isn't the model grading itself?"

**Metric C, "Door quad IoU" (optional).** Compare door masks with projected door quads. SAM 2's CUDA-kernel install step and uncertain MPS support make it risky on Macs. A cheaper deterministic proxy: the depth discontinuity or "see-through" region in a metric depth map (MoGe-2/DA3METRIC) inside the projected door quad.

**Metric D, "Depth agreement" (optional).** Render the twin's depth at the SfM pose and compare with MoGe-2/DA3METRIC depth. Use the median |log ratio| over pixels on walls. This is useful but noisier, since monocular depth error is roughly 10%.

**Why SSIM/LPIPS mislead here.** A flat-shaded twin and a textured photo differ everywhere in colour, lighting and clutter. Pixel and perceptual scores are dominated by that appearance gap and by furniture, and can improve or worsen without any geometry change. Keep them off the score, or show them only as a "don't trust this" foil.

**What to show live.** One chart per iteration: Metric A (illegal crossings, wall support %), Metric B on held-out frames, and Argon's discrepancy count, clearly labelled "model-reported". The loop's stop rule can include "the measured score did not improve", so Argon patches that worsen the geometry get rejected automatically. That is a real verification loop: the model proposes, geometry disposes.

### Gaps
- I found no published head-to-head of these specific metrics on phone walkthroughs. Thresholds (0.15 m, 5 px) are proposals to tune on the day's capture.
- Whether SAM 2's CUDA extension is optional on Mac (it appears to be only a post-processing kernel) was not confirmed.

---

## Q4. Rendering upgrades: Gaussian splatting from phone video and three.js viewers

### Takeaway
**Brush (Apache-2.0)** trains splats natively on Apple Silicon from COLMAP output. **Spark (MIT, World Labs)** renders splats and ordinary three.js meshes in one scene, so the graph (walls, door quads, flow arrows) can be overlaid *inside* a splat of the real room. Training a demo-quality splat should take tens of minutes on an M-series laptop. Caveat: Spark needs three.js r180+, and the plan pins `three@0.170.0`.

### Cited Findings
- Brush: Apache-2.0; macOS, Windows, Linux, AMD/Nvidia/Intel, Android and browser, via WebGPU and Burn. Takes COLMAP or Nerfstudio-format data. Exports `.ply` and `.compressed.ply`. Can compare the current rendering with input views during training. The web viewer streams `?url=`. Web training needs Chrome 134+ — [Brush GitHub](https://github.com/ArthurBrussee/brush).
- Brush 0.2 review: "on my M2, it's pulling about 17 steps a second" — [Radiance Fields, Brush 0.2](https://radiancefields.com/brush-0-2-released). OpenSplat on M2 took about 12 minutes for 2,000 steps and about 50 minutes for 7,000 — [Radiance Fields, OpenSplat on Mac](https://radiancefields.com/opensplat-3dgs-now-on-mac).
- OpenSplat is **AGPL-3.0** (repo now WebODM/OpenSplat) — GitHub API, [WebODM/OpenSplat](https://github.com/WebODM/OpenSplat).
- gsplat (Apache-2.0) and Nerfstudio (Apache-2.0) are CUDA-oriented. VGGT recommends `gsplat==1.3.0` on its COLMAP export — [gsplat](https://github.com/nerfstudio-project/gsplat); [nerfstudio](https://github.com/nerfstudio-project/nerfstudio); [VGGT README](https://github.com/facebookresearch/vggt).
- Spark: MIT; "Integrates with THREE.js rendering pipeline to fuse splat and mesh-based objects"; npm `@sparkjsdev/spark` — [Spark GitHub](https://github.com/sparkjsdev/spark). Reads PLY, SPZ, SPLAT, KSPLAT and SOG, and **requires three.js r180 or later** — [Radiance Fields, Spark](https://radiancefields.com/platforms/spark).
- mkkellogg GaussianSplats3D (MIT) "is no longer in active development", and its author recommends Spark — [GaussianSplats3D README](https://github.com/mkkellogg/GaussianSplats3D).

### Inferences
- **Pipeline:** the pycolmap poses from Q1 go to Brush (CLI, 5–7k steps, about 5–7 minutes at about 17 steps/s, my arithmetic from the M2 figure). Export `.ply` and load it in Spark in the Twin screen, applying the frozen SfM-to-graph similarity transform so the splat and graph line up in meters.
- **"X-ray" toggle:** a slider fades from splat (reality) to the twin's walls and door quads. Misaligned walls show visibly against the real room. This is the visual twin of Metric B.
- **Licensing:** Brush, Spark and pycolmap are all permissive. Avoid OpenSplat unless the team accepts AGPL. Skip Postshot (proprietary, not verified).
- **Version conflict:** bump the plan's `three@0.170.0` pin to ≥ 0.180 before Task 10 if Spark is adopted (lockfile owner: Codex).
- Train the splat on the pre-recorded SHACK15 run only. The judge's live clip should get poses and metrics, not a splat, given the training time.

### Gaps
- No measured Brush times on M3/M4 or for current versions. The 17 steps/s figure is from an early release on an unspecified M2 and resolution.
- Splat quality on a fast handheld walkthrough with motion blur and blank walls is unverified. Expect floaters.

---

## Q5. Crowd visualization faithful to solver counts, and an independent social-force cross-check

### Takeaway
Animate exactly the solver's integers: each unit of `door_flows[d][k]` becomes one dot crossing door d during step k. Dot counts then equal `reached_by_step` and `zone_occupancy` at every step, so there are no fake dots. **JuPedSim (LGPL-3.0, `pip install jupedsim`)** can serve as an independent microscopic cross-check of the max-flow result on the same geometry.

### Cited Findings
- JuPedSim: an open-source pedestrian dynamics simulator, installable with `pip install jupedsim`, licensed under GNU LGPLv3. A browser-based JuPedSim Web app also exists — [JuPedSim GitHub](https://github.com/PedestrianDynamics/jupedsim); [PyPI](https://pypi.org/project/jupedsim/); [FZ Jülich JuPedSim App](https://www.fz-juelich.de/en/ias/ias-7/services/software/jupedsim-app-en).
- The JuPedSim README notes it doesn't build against Python 3.13.4 on Windows (macOS not mentioned) — [JuPedSim README](https://github.com/PedestrianDynamics/jupedsim).

### Inferences
- **Faithful animation:** for step k, spawn `|door_flows[d][k]|` agents in the source zone and interpolate them along centroid → door → next-zone centroid over that door's `travel_steps`. Holdover people sit as jittered dots in the zone rect. Assert in a test that the rendered dot count per zone equals `zone_occupancy[k][zone]`, so the checker covers the animation too. Show the counter "dots = solver people, 1:1" on screen.
- **Cross-check with JuPedSim:** build zone rects as walkable polygons with door gaps from the graph, put exits at OUTSIDE doors, and seed occupants uniformly. Run its default operational model with the declared 1.2 m/s free speed, then compare "reached exit by 120 s" with the max-flow figure. Max-flow with a fixed specific flow is an idealised upper-bound style model, so the agent sim should come out at or below it. Show "max-flow 112 / agent-sim 104 (independent)". Disagreement is informative and honest. Label JuPedSim's number "independent model, not a measurement".
- LGPL as a pip dependency is fine for an MIT repo (dynamic use, no vendoring).

### Gaps
- I did not verify which operational models JuPedSim 1.x exposes (it reportedly offers collision-free speed and social-force variants) or its macOS arm64 wheel availability. Check `pip install jupedsim` on a team Mac early.
- Vadere was not researched (license and Python API unverified).
- No source located on the systematic gap between max-flow egress bounds and agent-based results for small rooms.

---

## Q6. Creative demo upgrades that raise "wow" while staying honest

### Takeaway
The strongest upgrade is turning the loop into **"Argon proposes, geometry disposes"**: show a measured score from SfM geometry and held-out frames that Argon never sees, alongside Argon's self-reported count. Then make it visual with an X-ray splat overlay, a trajectory "ghost" walking through the twin, and two-method agreement badges.

### Cited Findings
- The judging map weights the live demo with real inputs and a real verification loop at 50%. The plan currently labels the live loop score "model-reported", with the measured score coming only from the offline benchmark — [WalkTwin plan, local](/Users/charlie/hackathons/SpatialTwin/docs/superpowers/plans/2026-10-25-walkthrough-twin.md).
- Brush can show current renders against input views during training, and Spark fuses splats with meshes — [Brush](https://github.com/ArthurBrussee/brush); [Spark](https://github.com/sparkjsdev/spark).
- MapAnything and VGGT both have Gradio demos that accept images or video and show the reconstruction interactively — [MapAnything](https://github.com/facebookresearch/map-anything); [VGGT](https://github.com/facebookresearch/vggt).

### Inferences (proposals, ranked by value per hour)
1. **Measured loop score (Q3 Metric A plus held-out Metric B):** about 4–6 h. It directly upgrades the 50% criterion. Narration: "Argon said 2 discrepancies left. Geometry says 0 illegal wall crossings and 81% wall support on frames Argon never saw."
2. **The ghost walker:** play the SfM camera trajectory as a glowing camera frustum moving through the twin, synced to the video. Every time it passes through a wall without a door, flash red and show the timestamp: "you walked through a wall at 0:37, so Argon missed a door". Clicking the flash seeks the video, building on the plan's evidence seeking. Cheap once poses exist, and very legible.
3. **Two independent methods, agreement badges:**
   - door width: Argon's range against triangulated jamb-to-jamb distance from SfM plus anchor scale
   - room extent: Argon's rect against the SfM density-map extent
   - scale: anchor against metric depth against eye height
   - egress: max-flow against JuPedSim

   Show green "agree within X" or amber "disagree, cannot measure". Disagreement shown openly builds trust with judges.
4. **X-ray slider:** in the Loop screen, the video frame with the projected twin edges drawn on top (Metric B's overlay) before and after each patch. The lines visibly snap onto real door frames as iterations proceed. The splat version can be pre-built for the SHACK15 saved run.
5. **The judge's walk becomes the twin:** keep the plan's 45 s capture, but process the judge's clip through pycolmap first, since SfM is local and should take minutes (estimate). That way the ghost walker and the geometry score appear while Argon's extraction still runs, and the judge sees their own path traced in 3D early.
6. **Time-scrubbing evidence:** a timeline under the twin where each door or zone is a bar spanning its evidence intervals, plus SfM camera-path ticks. Scrubbing moves the ghost camera and the video together.
7. **"Adversarial" moment (optional):** a teammate deletes a door in the graph live. The measured score drops (illegal crossings appear), the loop runs, and Argon proposes re-adding it. Geometry confirms it, the score returns, and the patch is accepted with a checker receipt.
8. **Honest crowd animation:** dots driven 1:1 by `door_flows`, a counter reconciled each step, and the JuPedSim number beside it as an independent model.

**Licensing guardrails:** don't ship or download DUSt3R, MASt3R, MASt3R-SLAM, CUT3R, the original VGGT-1B, Pi3/Pi3X weights, UniDepth, Depth Pro, SceneScript, SpatialLM encoder weights, DA3-LARGE/GIANT/NESTED or DA-V2 Base/Large weights in a public repo or demo. Permissive picks: pycolmap/COLMAP/GLOMAP (BSD), MapAnything-apache, DA3-BASE/SMALL/METRIC-LARGE (Apache-2.0), MoGe-2 (MIT), DA-V2 Small (Apache-2.0), SAM 2 (Apache-2.0), Brush (Apache-2.0), Spark (MIT), JuPedSim (LGPL-3.0), OpenCV LSD (restored under MIT-compatible terms), DeepLSD (MIT), RoomFormer and HorizonNet (MIT).

### Gaps
- Timings for SfM, Brush and MapAnything on the team's actual MacBooks are unknown. Run a 20 s probe clip through pycolmap at kickoff, alongside the plan's Task 2 API probes, and set narration from measured times.
- Low-texture venues (white walls, glass) can break SIFT SfM. MapAnything-apache or DA3-BASE are the fallback, but their MPS speed is unmeasured.
