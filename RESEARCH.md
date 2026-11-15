# Can a generated world stay itself?

Imagine describing a place, stepping inside, and learning with a lifelike guide. Turn away, return, open a door or change something by speaking: it should still be the same world.

That is Sciescape's goal. The immediate research question is more precise:

**Can one persistent 3D scene state keep appearance, movement, edits and a guide's understanding consistent?**

## The idea to test

Give rooms, surfaces, openings and objects stable identities. Rendering, movement and the guide read the same evolving state. Check a generated change before exposing it to the visitor, preserve unaffected structure, and regenerate appearance locally where possible.

Text-to-3D and explicit geometry already exist. [Text2Room](https://lukashoel.github.io/text-to-room/) generates textured room meshes; [DreamScene360](https://dreamscene360.github.io/) creates panoramic 3D scenes. The proposed contribution is a measurable improvement in interactive consistency, with its compute and latency costs made explicit. It is a hypothesis, not an established breakthrough.

## A bounded evaluation

- Compare the proposed method, the current depth-panorama pipeline, an ablation with separate interaction state, and a runnable, licence-compatible public comparator.
- Freeze 21 new requests, two seeds, movement/editing scripts, versions and scoring before evaluation. Keep development scenes separate.
- Count timeouts and refused requests as failures. Check passage through doorways, return visits, persistent changes, visible-object references, guide footing and scene membership.
- Measure quality, latency and GPU memory together. A more convincing picture that breaks interaction is not a successful complete journey.
- Compare two avatar candidates with matched views, expressions and browser performance, after licence checks.

The proposed allocation is 100 single-GPU hours: 24 for implementation and compatibility checks, 42 for the fixed comparison, 18 for avatar tests, 10 for integrated journeys and six for bounded recovery. CPU replay runs off the GPU. Stop or reduce scope if the protocol cannot fit the available allocation.

The main hypothesis fails if shared state does not improve held-out complete journeys at a useful quality/latency trade-off. Failures will remain in the report. The exact scoring thresholds and comparator choice will be frozen before this new study runs; this page is a proposal, not a completed preregistration.

## A separate voice-reliability study

Compare speech alone, speech with the current image, and speech with both the image and explicit scene state. Use 20 new scenes and four tasks, for 240 evaluation sessions plus at most 36 pilots/retries. Each session lasts at most three minutes. Measure incorrect visual references, recovery after changes, interruption handling and response time against independent rendered evidence.

Use synthetic scenes and licensed voices. No human participants, private recordings or real-person likenesses are part of this study. Technical tests cannot establish learning gains, appropriate trust or perceived naturalness; those would need a separate human study.

## What is open now

This repository contains selected original scene outputs, provenance, the static showcase and an Apache-2.0 resumable batch utility with tests. It will host permitted evaluation material as the study develops. The product repository, credentials, restricted assets and model weights are outside this release.

Sciescape is Navish Kumar's personal research project. University of Basel is an academic affiliation, not a claimed sponsor of this work. [Research profile](https://kumarnavish.github.io).
