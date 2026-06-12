"""Modal app: serves NVIDIA Nemotron 30B-A3B behind Ollama's native API on a
dedicated L40S GPU, with per-second billing and scale-to-zero.

This is how the hosted HF Space runs the real model: the Space itself stays on
free cpu-basic hardware and points OLLAMA_HOST at this endpoint — the engine's
existing Ollama path works unchanged (it speaks /api/chat either way).

Why L40S: the 30B-A3B is a Mixture-of-Experts (only ~3B params active per token,
so it's fast), but ALL ~24 GB of Q4 weights must sit in VRAM — a 24 GB card
doesn't fit; the L40S (48 GB) does, with room for KV cache.

One-time setup (downloads the weights into a persistent Volume):
    modal run modal_ollama.py::pull

Deploy the endpoint:
    modal deploy modal_ollama.py
    # -> https://<workspace>--global-leaders-ollama-serve.modal.run

Then set on the HF Space (or local .env):
    OLLAMA_HOST=<that URL>
    OLLAMA_MODEL=nemotron-3-nano:30b

Idle behaviour: after SCALEDOWN_S without traffic the container stops and costs
$0. The next request wakes it (~30-60 s once: container boot + weights to VRAM);
the game backend's 120 s timeout and retries absorb that first slow call.
"""

import subprocess
import time
import urllib.request

import modal

MODEL = "nemotron-3-nano:30b"
PORT = 11434
SCALEDOWN_S = 20 * 60  # stay warm 20 min after the last request, then scale to zero

app = modal.App("global-leaders-ollama")

# The stock ollama/ollama image, plus the Python runtime Modal needs inside containers.
image = (
    modal.Image.from_registry("ollama/ollama:0.30.8", add_python="3.12")
    .entrypoint([])
    .env({"OLLAMA_HOST": "0.0.0.0:11434"})  # bind beyond loopback so Modal can proxy it
)

# Weights live here across runs — cold starts load from disk, never re-download 24 GB.
volume = modal.Volume.from_name("global-leaders-ollama-models", create_if_missing=True)
VOL_PATH = "/root/.ollama"


def _wait_for_daemon(timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/tags", timeout=2)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError("ollama daemon did not come up")


@app.function(image=image, volumes={VOL_PATH: volume}, timeout=60 * 60)
def pull():
    """One-shot: download the model into the Volume (no GPU billed for this)."""
    subprocess.Popen(["ollama", "serve"])
    _wait_for_daemon()
    subprocess.run(["ollama", "pull", MODEL], check=True)
    volume.commit()
    print(f"{MODEL} stored in volume.")


@app.function(
    image=image,
    gpu="L40S",
    volumes={VOL_PATH: volume},
    scaledown_window=SCALEDOWN_S,
    max_containers=1,  # one GPU at a time — a queue beats surprise parallel billing
)
@modal.concurrent(max_inputs=20)  # many players share the one container; Ollama queues
@modal.web_server(port=PORT, startup_timeout=180)
def serve():
    subprocess.Popen(["ollama", "serve"])
    _wait_for_daemon()
    # Pre-load weights into VRAM so the wake-up request pays the load once, here,
    # instead of on the player's first move.
    urllib.request.urlopen(
        urllib.request.Request(
            f"http://127.0.0.1:{PORT}/api/generate",
            data=b'{"model": "' + MODEL.encode() + b'", "keep_alive": -1}',
            headers={"Content-Type": "application/json"},
        ),
        timeout=120,
    )
