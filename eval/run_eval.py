"""Run every case of a split through the real pipeline and score it.

    python eval/run_eval.py --split dev
    python eval/run_eval.py --split dev --model meta-llama/Llama-3.3-70B-Instruct

Writes eval/results/<run-name>/ with config.json, traces.jsonl,
metrics.json and report.md. A run that stops halfway can be resumed by
passing the same --run-name.

The test split is locked (EVAL_SPEC.md §7): running it requires
--use-test-set, and should only happen for final comparisons.
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, HERE)


def git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "app", "eval/datasets"],
                               cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return out + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--model", default=None, help="text model id (default: the app's default)")
    ap.add_argument("--temperature", default="0",
                    help="a number, or 'default' to use the provider's default temperature")
    ap.add_argument("--repeat", type=int, default=None, help="repeat index for variance runs (1, 2, 3)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N cases (smoke test)")
    ap.add_argument("--run-name", default=None)
    ap.add_argument("--use-test-set", action="store_true", help="required to run the locked test split")
    ap.add_argument("--sleep", type=float, default=0.0, help="pause between cases (rate limits)")
    args = ap.parse_args(argv)

    if args.split == "test" and not args.use_test_set:
        sys.exit("The test split is locked. Re-run with --use-test-set only for final results.")

    import pipeline
    from pipeline import config as pcfg
    from score import load_cases, score_run

    model = args.model or pcfg.DEFAULT_TEXT_MODEL
    slug = model.split("/")[-1].lower()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    temperature = None if str(args.temperature).lower() == "default" else float(args.temperature)
    t_tag = "tdefault" if temperature is None else f"t{temperature:g}"
    tag = "" if pcfg.TRIAGE_ENABLED else "_notriage"
    if pcfg.TRIAGE_ENABLED and pcfg.TRIAGE_MODEL:
        tag += "_triage-" + pcfg.TRIAGE_MODEL.split("/")[-1].lower()
    if args.repeat:
        tag += f"_r{args.repeat}"
    run_name = args.run_name or f"{stamp}_{args.split}_{slug}_{t_tag}{tag}"
    run_dir = os.path.join(HERE, "results", run_name)
    os.makedirs(run_dir, exist_ok=True)

    cases = list(load_cases(args.split).values())
    if args.limit:
        cases = cases[:args.limit]

    print("Loading catalog and embedding model...")
    pipeline.load()
    if not pipeline.is_ready():
        from pipeline import catalog
        sys.exit(f"Pipeline failed to start: {catalog.STATE['error']}")

    cfg_path = os.path.join(run_dir, "config.json")
    if not os.path.exists(cfg_path):
        config = {
            "run_name": run_name, "split": args.split, "n_cases": len(cases), "model": model,
            "temperature": temperature, "repeat": args.repeat, "embedding_model": pcfg.EMBEDDING_MODEL,
            "concern_threshold": pcfg.CONCERN_THRESHOLD, "n_products": pcfg.N_PRODUCTS,
            "backend": "huggingface" if pcfg.USE_HF else "databricks",
            "triage_enabled": pcfg.TRIAGE_ENABLED,
            "triage_model": (pcfg.TRIAGE_MODEL or model) if pcfg.TRIAGE_ENABLED else None,
            "triage_prompt_version": __import__("pipeline.triage", fromlist=["x"]).PROMPT_VERSION
            if pcfg.TRIAGE_ENABLED else None,
            "git_commit": git_commit(),
            "dataset_hash": file_hash(os.path.join(HERE, "datasets", f"{args.split}.jsonl")),
            "catalog_hash": file_hash(os.path.join(ROOT, "app", "app_data.json")),
            "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=1)

    traces_path = os.path.join(run_dir, "traces.jsonl")
    done = set()
    if os.path.exists(traces_path):
        with open(traces_path, encoding="utf-8") as f:
            done = {json.loads(line)["case_id"] for line in f if line.strip()}

    todo = [c for c in cases if c["id"] not in done]
    print(f"Running {len(todo)} cases ({len(done)} already done) with {model}")
    with open(traces_path, "a", encoding="utf-8") as f:
        for i, case in enumerate(todo, 1):
            try:
                trace = pipeline.run_pipeline(case["query"], model=model, temperature=temperature)
            except Exception as e:  # a crash is itself a measured failure (gate: 0)
                trace = {"status": "crash", "error": f"{type(e).__name__}: {e}", "answer": None}
            trace["case_id"] = case["id"]
            trace.pop("concern_scores", None)
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  [{i}/{len(todo)}] {case['id']:22s} {trace.get('status')}")
            if args.sleep:
                time.sleep(args.sleep)

    result = score_run(run_dir)
    gates = [v for v in result["verdicts"] if v["kind"] == "gate"]
    print(f"\nGates passed: {sum(1 for v in gates if v['passed'])}/{len(gates)}")
    for v in result["verdicts"]:
        flag = "—   " if v["passed"] is None else ("PASS" if v["passed"] else "FAIL")
        val = "—" if v["value"] is None else f"{v['value']:.3f}"
        print(f"  {v['kind']:6s} {flag} {v['label']}: {val}")
    print(f"\nReport: {os.path.relpath(os.path.join(run_dir, 'report.md'), ROOT)}")


if __name__ == "__main__":
    main()
