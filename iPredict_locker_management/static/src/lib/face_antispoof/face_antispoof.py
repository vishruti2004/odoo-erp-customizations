# -*- coding: utf-8 -*-

import sys
import cv2
import numpy as np
import onnxruntime as ort


def softmax(x):
    x = x - np.max(x)
    e = np.exp(x)
    return e / np.sum(e)


def run_model(session, input_name, output_name, tensor):
    output = session.run([output_name], {input_name: tensor})[0]
    scores = np.asarray(output, dtype=np.float32).reshape(-1)
    print("  RAW OUTPUT:", scores)
    if scores.size == 3:
        probs = softmax(scores) if (
            np.any(scores < 0) or np.any(scores > 1)
        ) else scores
        print("  PROBS: print=%.4f live=%.4f replay=%.4f" % (
            probs[0], probs[1], probs[2]
        ))
    return scores


def to_tensor(face_80x80_bgr, mode):
    face = face_80x80_bgr.astype(np.float32)
    if mode == "div255":
        face = face / 255.0
    elif mode == "insightface_norm":
        face = (face - 127.5) / 128.0
    elif mode == "rgb_div255":
        face = face[:, :, ::-1] / 255.0  # BGR -> RGB
    else:
        raise ValueError(mode)
    face = np.transpose(face, (2, 0, 1))
    face = np.expand_dims(face, axis=0)
    return np.ascontiguousarray(face)


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 test_antispoof.py <model.onnx> <face_crop.jpg>")
        sys.exit(1)

    model_path = sys.argv[1]
    image_path = sys.argv[2]

    print("Loading model:", model_path)
    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    print("Input:", session.get_inputs()[0].shape)
    print("Output:", session.get_outputs()[0].shape)

    face = cv2.imread(image_path)
    if face is None:
        print("Could not read image:", image_path)
        sys.exit(1)
    face = cv2.resize(face, (80, 80), interpolation=cv2.INTER_LINEAR)

    print("\n=== Real captured face crop ===")
    for mode in ("div255", "insightface_norm", "rgb_div255"):
        print(f"-- normalization: {mode} --")
        run_model(session, input_name, output_name, to_tensor(face, mode))

    # Sanity check: does the model even respond to wildly different inputs?
    print("\n=== Sanity check: does output change with different inputs? ===")

    black = np.zeros((80, 80, 3), dtype=np.uint8)
    white = np.full((80, 80, 3), 255, dtype=np.uint8)
    noise = np.random.randint(0, 256, (80, 80, 3), dtype=np.uint8)

    for name, img in (("all-black", black), ("all-white", white), ("random-noise", noise)):
        print(f"-- input: {name} (div255 normalization) --")
        run_model(session, input_name, output_name, to_tensor(img, "div255"))


if __name__ == "__main__":
    main()