"""Download immutable, licensed Spanish voice weights outside version control."""

MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit"
REVISION = "5c390979e4b93af5f2932f90742ca99c7dd04687"


def download():
    from huggingface_hub import snapshot_download

    return snapshot_download(MODEL, revision=REVISION)


if __name__ == "__main__":
    print(download())
