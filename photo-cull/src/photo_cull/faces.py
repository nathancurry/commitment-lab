"""Face and open-eye detection (CPU, OpenCV Haar cascades).

Stage-1 closed-eye heuristic: detect frontal faces; within the upper part
of each face look for open eyes with the eye cascade. A face where no
open eye is found raises the ``eyes_closed_suspect`` flag. This is a
coarse heuristic — it never rejects, it only asks for a look — and its
thresholds await calibration on real photos (stage 2 / sample set).

The decision logic is a pure function so it can be tested without OpenCV.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_FACE_CASCADE = "haarcascade_frontalface_default.xml"
_EYE_CASCADE = "haarcascade_eye.xml"

# Detection parameters (on the 1024-normalized grayscale).
_FACE_SCALE = 1.1
_FACE_NEIGHBORS = 6
_FACE_MIN_SIZE = 64
_EYE_SCALE = 1.1
_EYE_NEIGHBORS = 3
_EYE_MIN_SIZE = 16
# Eyes live in the top 60% of a frontal face box.
_EYE_REGION_FRACTION = 0.6


def available() -> bool:
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass
class FaceObservation:
    """One detected face and how many open eyes were found in it."""

    box: tuple[int, int, int, int]
    open_eyes: int = 0


@dataclass
class FaceReport:
    faces: int
    open_eyes: int
    flags: list[str] = field(default_factory=list)


def eye_flags(observations: list[FaceObservation]) -> list[str]:
    """Pure decision: which flags follow from the face/eye observations."""
    if not observations:
        return []
    if all(obs.open_eyes == 0 for obs in observations):
        return ["eyes_closed_suspect"]
    return []


def _load_cascades():
    import cv2

    face = cv2.CascadeClassifier(cv2.data.haarcascades + _FACE_CASCADE)
    eye = cv2.CascadeClassifier(cv2.data.haarcascades + _EYE_CASCADE)
    if face.empty() or eye.empty():
        raise RuntimeError("OpenCV Haar cascades failed to load")
    return face, eye


def _eye_region(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, w, h = box
    return (x, y, w, max(1, round(h * _EYE_REGION_FRACTION)))


def detect_faces(gray) -> list[FaceObservation]:
    """Run the cascades on a normalized grayscale array."""
    import cv2

    face_cascade, eye_cascade = _load_cascades()
    enhanced = cv2.equalizeHist(gray)
    faces = face_cascade.detectMultiScale(
        enhanced,
        scaleFactor=_FACE_SCALE,
        minNeighbors=_FACE_NEIGHBORS,
        minSize=(_FACE_MIN_SIZE, _FACE_MIN_SIZE),
    )
    observations: list[FaceObservation] = []
    for box in faces:
        x, y, w, h = (int(v) for v in box)
        ex, ey, ew, eh = _eye_region((x, y, w, h))
        eyes = eye_cascade.detectMultiScale(
            enhanced[ey:ey + eh, ex:ex + ew],
            scaleFactor=_EYE_SCALE,
            minNeighbors=_EYE_NEIGHBORS,
            minSize=(_EYE_MIN_SIZE, _EYE_MIN_SIZE),
        )
        observations.append(FaceObservation(box=(x, y, w, h), open_eyes=len(eyes)))
    return observations


def assess_faces(gray) -> FaceReport:
    """Detect faces and open eyes; attach the closed-eye flag."""
    observations = detect_faces(gray)
    return FaceReport(
        faces=len(observations),
        open_eyes=sum(obs.open_eyes for obs in observations),
        flags=eye_flags(observations),
    )
