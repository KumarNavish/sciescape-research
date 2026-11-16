# Somewhere starts with a sentence

An 84-second research film by Navish Kumar / Sciescape, 16 November 2026.

[Watch](https://kumarnavish.github.io/sciescape-research/#film) · [MP4](../assets/sciescape-film.mp4) · [Timed text](../assets/film-captions.vtt) · [Source manifest](../evidence/film.json)

The film presents selected real outputs and a research ambition. It is not a recording of a complete live product journey. Titles identify the existing prototype, the recorded baseline experiment, and the unsolved research goal. No new model generation or paid API call was used to produce the film.

## What is shown

- **0–28 seconds:** original Sciescape panoramas, viewed through a perspective camera rotating at one position. There is no invented forward motion or geometry. The source images remain unchanged; film framing, titles, fades and a lower title shadow are editorial additions.
- **28–40 seconds:** a contiguous 3–15 second excerpt from the archived FlashWorld baseline render, at original speed. The full source frame is preserved with side borders. Frame duplication converts 15 fps to the film's 24 fps. This is actual Gaussian-scene camera-path rendering, not an application walkthrough or a claim of a new Sciescape method.
- **40–84 seconds:** the research gap and goal over original panoramas. Persistent edits, a lifelike avatar and integrated natural voice are goals, not demonstrated achievements. The 2/21 result is an archived development evaluation, not held-out performance.

## Attribution and licence

**The film, original soundtrack and recorded FlashWorld excerpt are shared for noncommercial research and inspection under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), to the extent the contributors hold the relevant rights.** This is not a claim that all machine-generated material attracts copyright. Source code is Apache-2.0. Existing panorama files retain their separate [CC BY 4.0 terms](../MEDIA_LICENSE.md).

Credit: **Sciescape / Navish Kumar, 2026.** Panorama generation uses **Qwen-Image (Alibaba/Qwen), QwenImage360 (CedarC), and Qwen-Image-Lightning (LightX2V)**. Their revisions, original-image hashes and receipts are in [the evidence record](../EVIDENCE.md).

The 3D scene uses **FlashWorld: High-quality 3D Scene Generation within Seconds**, by **Xinyang Li, Tengfei Wang, Zixiao Gu, Shengchuan Zhang, Chunchao Guo and Liujuan Cao**, ICLR 2026. [Official model revision and licence](https://huggingface.co/imlixinyang/FlashWorld/tree/6a8e88c6f88678ac098e4c82675f0aee555d6e5d). Archived generation logs identify that exact weight revision; the scene was generated from text without an input image. No weights are redistributed.

The original source clip has SHA-256 `0698c423d5f458498a2e0f642d315ddf95a359d31587b0e82af51acbfd6c085b`; archived code revision `424db4487de308a39e5137afbe85e7568a96193f`. The public manifest exports only non-sensitive provenance. The film does not use Lyra or LAM footage, private recordings, real-person likenesses, commercial music, or third-party audio samples.

## Reproduce

```sh
python3 film/build_film.py --preview --width 1280
python3 film/build_film.py
```

Requirements: Python 3, NumPy, Pillow, OpenCV and FFmpeg with H.264/AAC encoding. The renderer streams frames to FFmpeg, keeps no image sequence and uses at most two OpenCV and encoder threads. Temporary soundtrack data is removed after encoding. It uses installed system fonts (Avenir Next / Didot on macOS; DejaVu fallbacks on Linux). Original music is synthesized by the source script, with no external model or sample service.

The camera construction and visual references are documented in `evidence/film.json`. The public site loads no video until playback is requested, and pauses it on page hiding or panorama entry.
