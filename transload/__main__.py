import subprocess
import sqlite3 as sql
import time
from transload import config as cfg
import os


class MusicDB:
    def __init__(self) -> None:
        print("Starting database...")
        db_path = cfg.db_location

        self.connection = sql.connect(db_path)
        self.connection.row_factory = sql.Row
        self.cursor = self.connection.cursor()

        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS uploads (file_name TEXT PRIMARY KEY, synced BOOLEAN NOT NULL CHECK (synced IN (0, 1)))"
        )

        self.commit()

    def commit(self):
        self.connection.commit()

    def kill(self):
        self.cursor.close()
        self.connection.close()

    def add_track(self, filename: str):
        self.cursor.execute(f'INSERT INTO uploads VALUES("{filename},1")')

    def get_tracks(self):
        tracks = []
        self.cursor.execute("SELECT * FROM uploads")
        result = self.cursor.fetchall()

        for track in result:
            tracks.append(track)

        return tracks

    def track_exists(self, filename: str):
        exists = False
        try:
            self.cursor.execute(f'SELECT * FROM uploads WHERE filename="{filename}"')
            result = self.cursor.fetchone()[0]
            if result:
                exists = True
        except Exception as e:
            pass

        return exists


def upload(db: MusicDB):
    to_upload = []
    synced = []
    tracks = db.get_tracks()

    print("Scanning files to upload...")
    for current_dir, folders, files in os.walk(cfg.lib_local):
        for file in files:
            if file.endswith(cfg.ext_local) and file not in tracks:
                synced.append(file)
                to_upload.append(os.path.abspath(os.path.join(current_dir, file)))

    print("Processing files...")
    for file in to_upload:
        codec = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=nokey=1:noprint_wrappers=1",
                file,
            ]
        )

        if cfg.ext_local.replace(".", "") in str(codec):
            target = os.path.join(
                cfg.lib_remote,
                os.path.basename(file.replace(cfg.ext_local, cfg.ext_remote)),
            )
            attempts = 0
            while True:
                try:
                    subprocess.call(
                        [
                            "ffmpeg",
                            "-i",
                            file,
                            "-c:a",
                            cfg.ffmpeg_target,
                            "-c:v",
                            "copy",
                            target,
                        ]
                    )
                    attempts += 1
                    break
                except:
                    if attempts >= 10:
                        print(
                            f"Transcode failed 10 times! Skipping track {file} for now..."
                        )

                    if os.path.exists(target):
                        os.remove(target)
                    print(
                        "Yikes! Got stuck while transcoding. Trying again after a 1 minute break."
                    )
                    time.sleep(60)

            db.add_track(synced[to_upload.index(file)])


def main():
    db = MusicDB()
    upload(db)
    db.kill()
    input("Done! Enjoy your music")


if __name__ == "__main__":
    main()
