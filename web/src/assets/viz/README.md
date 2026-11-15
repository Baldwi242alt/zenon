# Visualizations (illustrative, not data)

Everything in this folder is an AI-generated illustration made with Higgsfield, labelled on the
website as "Illustrative · Higgsfield visualization". All data and all photographs elsewhere on the
site come from NASA (LRO LOLA, LROC, JPL Horizons, NASA Image Library).

| File | Made with | Prompt (summary) |
| --- | --- | --- |
| `rover_ridge.jpg` | GPT Image 2.6 | Six-wheeled rover with a vertical solar panel on a south-pole ridge, Sun on the horizon, long shadows |
| `shadow/f*.webp` | Kling 3.0 (text to video), 8 s, frames at 9 fps | Time-lapse: low Sun sliding along a crater-rim horizon, shadows sweeping across regolith |
| `rover/f*.webp` | Kling 3.0 (image to video from `rover_ridge.jpg`), 8 s, frames at 9 fps | The rover drives along the ridge, its panel turning to follow the Sun |

The frames are scrubbed by scroll position (`web/src/story/Scrub.tsx`).
| `regolith.jpg` | GPT Image 2.6 | Seamless top-down lunar regolith grain, used only as surface detail on the 3D terrain (heights and shadows there are real data) |
| `polar_dawn.webp` | Frame 36 of `shadow/` | Header image for the Landing windows page |
| `rover_loop.mp4`, `shadow_loop.mp4` | Re-encodes of the two Kling videos above | Muted looping headers for the Rover and Landing windows pages |
