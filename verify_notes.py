import asyncio
import os
from telegram_bot.infrastructure.file_note_repository import FileNoteRepository
from telegram_bot.services.note_service import NoteService

async def main():
    test_file = "data/test_notes.json"
    if os.path.exists(test_file):
        os.remove(test_file)

    repo = FileNoteRepository(test_file)
    service = NoteService(repo)

    print("1. Testing Add Note...")
    note1 = await service.add_note("Math Notes", "Algebra formulas", "http://math.com")
    print(f"Added: {note1}")

    print("\n2. Testing Get All Notes...")
    notes = await service.get_all_notes()
    print(f"Retrieved {len(notes)} notes.")
    assert len(notes) == 1
    assert notes[0].title == "Math Notes"

    print("\n3. Testing Persistence...")
    # Re-instantiate to check file read
    repo2 = FileNoteRepository(test_file)
    service2 = NoteService(repo2)
    notes2 = await service2.get_all_notes()
    print(f"Retrieved {len(notes2)} notes from disk.")
    assert len(notes2) == 1
    assert notes2[0].content == "Algebra formulas"

    print("\n✅ Verification Successful!")
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)

if __name__ == "__main__":
    asyncio.run(main())
