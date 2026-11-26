"""Settings find backend/.env whichever folder the API or worker is started from."""
from pathlib import Path

from annotator.config.settings import Settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_settings_file_is_backend_env():
    assert Path(Settings.model_config["env_file"]) == BACKEND_DIR / ".env"


def test_a_settings_file_in_the_start_folder_is_ignored(tmp_path, monkeypatch):
    # Started from another folder (e.g. claude-annotator/) that has its own .env.
    (tmp_path / ".env").write_text("GEMINI_API_KEY=decoy-from-start-folder\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    key = Settings().gemini_api_key  # a plain value, so a failure never prints other settings
    assert key != "decoy-from-start-folder"
