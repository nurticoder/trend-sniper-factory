from typing import Literal

from pydantic import BaseModel, ConfigDict


class VoicePreference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    narration: Literal["auto", "off", "required"]


def install(app, store):
    with store.connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS production_preferences(slot INTEGER PRIMARY KEY, narration TEXT NOT NULL)"
        )
        db.execute("INSERT OR IGNORE INTO production_preferences VALUES (1,'auto')")

    def preferences():
        with store.connection() as db:
            mode = db.execute(
                "SELECT narration FROM production_preferences WHERE slot=1"
            ).fetchone()[0]
        return {"narration": mode}

    app.state.production_preferences = preferences

    @app.get("/api/production-preferences")
    def read():
        return preferences()

    @app.put("/api/production-preferences")
    def update(body: VoicePreference):
        with store.connection() as db:
            db.execute(
                "UPDATE production_preferences SET narration=? WHERE slot=1",
                (body.narration,),
            )
        return preferences()
