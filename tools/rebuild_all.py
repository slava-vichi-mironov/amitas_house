"""Re-extract walls from the PDF and rebuild viewer/house.json."""
import subprocess
import sys

FLOORS = ("ground", "first", "stairroom", "roof")


def main():
    for floor in FLOORS:
        print(f"== extract {floor} ==")
        subprocess.check_call([sys.executable, "tools/extract_walls.py", floor])
    print("== build model ==")
    subprocess.check_call([sys.executable, "tools/build_model.py"])
    print("done -> viewer/house.json")


if __name__ == "__main__":
    main()
