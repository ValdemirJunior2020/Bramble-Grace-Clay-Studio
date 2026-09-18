# ComfyUI workflow adapters

Clay Studio does not require you to edit ComfyUI nodes. Optional AI workflows live here as two files:

- `<name>.json` — a ComfyUI **API-format** workflow exported from ComfyUI.
- `<name>.adapter.json` — maps Clay Studio values to node IDs and fields.

Example adapter shape:

```json
{
  "name": "My local image-to-video workflow",
  "workflow": "my-workflow.json",
  "minimum_vram_gb": 12,
  "output_node": "99",
  "mapping": {
    "input_image": {"node": "1", "field": "image"},
    "audio": {"node": "2", "field": "audio"},
    "prompt": {"node": "3", "field": "text"},
    "negative_prompt": {"node": "4", "field": "text"},
    "seed": {"node": "5", "field": "seed"},
    "width": {"node": "6", "field": "width"},
    "height": {"node": "6", "field": "height"}
  }
}
```

No untested workflow JSON is bundled and labeled as working. Add a workflow only after its nodes/models are installed locally and verified.
