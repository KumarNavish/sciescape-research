# What you can inspect today

Five generated places. A reusable, tested research utility. A clear record of what remains unsolved.

This is a curated release from Sciescape, Navish Kumar's independent research project. The main development repository remains private. The media below are original archived outputs, copied without retouching or regeneration.

## From words to a surrounding scene

| Place | Image | Archived worker stage |
| --- | --- | ---: |
| Bamboo after rain | [Full panorama](assets/bamboo.png) | 24.778 s |
| Canal at dusk | [Full panorama](assets/canal.png) | 24.806 s |
| Mountain hut | [Full panorama](assets/hut.png) | 29.615 s |
| Quiet reading room | [Full panorama](assets/reading-room.png) | 26.123 s |
| Desert oasis | [Full panorama](assets/oasis.png) | 24.610 s |

Each archived receipt records a completed text-to-panorama path, 24 depth views and a constructed 750,000-splat scene asset. This release includes the 1920 × 960 panorama images. It does not include the larger scene assets, model weights or a live inference service.

The times are recorded worker stages, not cold-start time or complete visitor response latency. These five selected scenes demonstrate visual generation; they are not a random sample or a benchmark of navigation reliability. A flat panorama also stretches its poles. The cover crops the original image through CSS; the gallery opens the full original.

[Machine-readable provenance and hashes](evidence/gallery.json) identify every image and source job. Local archived receipts were checked before release. Only the relevant fields are exported; private logs and infrastructure details are excluded.

### Generators and attribution

The images were generated with existing models, not a foundation model trained by Sciescape:

- [Qwen-Image — Alibaba/Qwen](https://huggingface.co/Qwen/Qwen-Image/blob/75e0b4be04f60ec59a75f475837eced720f823b6/LICENSE), revision `75e0b4be04f60ec59a75f475837eced720f823b6`.
- [QwenImage360 — CedarC](https://huggingface.co/CedarC/QwenImage360/blob/bb4cb1d4c24c404edde27b76641d7ca12f1b4398/README.md), revision `bb4cb1d4c24c404edde27b76641d7ca12f1b4398`.
- [Qwen-Image-Lightning — LightX2V](https://huggingface.co/lightx2v/Qwen-Image-Lightning/blob/d468c534b360e0754c6bf9e38ed49e1e09cd2e2a/README.md), revision `d468c534b360e0754c6bf9e38ed49e1e09cd2e2a`.

Their published licence declarations were checked as Apache-2.0 on 15 November 2026. Model licences and generated-media rights are distinct; no model weights are redistributed here. See [media terms](MEDIA_LICENSE.md).

## A practical tool for limited compute

[The batch runtime](research/batch_runtime.py) preserves completed cases across interruptions, checks artifact hashes, rejects changed run identities and duplicate writers, and bounds child processes with a deadline. It never allocates cloud resources.

Its [23 CPU tests](tests/test_batch_runtime.py) passed on macOS on 15 November 2026, including interruption/resume, corrupted artifacts, deadline expiry and child cleanup:

```sh
python3 -B -m unittest discover -s tests -p test_batch_runtime.py -v
```

The runtime is an unchanged export from source revision `6af6e3ce4c5b84a0f17a2ced4d3b4ab6a8e15183`, SHA-256 `aa4e45933f3f074cc50d030dd926c1d85e0481a6852f868509a8f1f9f3b2ebfe`. The tests only change their import path and retain an adaptation notice. This is a useful reliability component, not a cloud billing cap or evidence that the immersive experience is solved.

## What remains open

The latest saved geometry evaluation completed 2 of 21 development cases against a target of 17. Those scenes had informed development, so they are not independent validation. A stronger avatar has not yet passed the shared speech-driver comparison. The complete natural-voice, freely navigable experience remains under development.

These failures motivate the next study: a persistent scene representation shared by rendering, movement, edits and the guide. See [the research plan](RESEARCH.md). No publication, novelty or human/Quest acceptance claim is made from this gallery.
