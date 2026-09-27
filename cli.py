import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

from ai_evals.core.run_manager import RunManager, digest
from ai_evals.core.runner import run
from ai_evals.evals.ifeval.dataset import DATA, SOURCE, SUITE, load_dataset, summarize, tasks_from_rows
from ai_evals.evals.ifeval.grader import grade_run, official_modules
from ai_evals.evals.ifeval.analysis import analyze
from ai_evals.providers.deepseek import DeepSeekProvider
from ai_evals.providers.qwen import QwenProvider

ROOT = Path(__file__).resolve().parent


def provider_for(config):
    cls = {"deepseek": DeepSeekProvider, "qwen": QwenProvider}[config["provider"]]
    provider = cls(base_url=config["base_url"], timeout=config["timeout_seconds"])
    if not os.environ.get(provider.key_env):
        raise ValueError(f"Set {provider.key_env} in the environment or .env before running")
    return provider


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI Eval Workspace V1")
    parser.add_argument("--workspace", type=Path, default=ROOT, help="Root containing .env, runs, reports")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="Verify official files and summarize the dataset")
    prepare.add_argument("--download-nltk", action="store_true", help="Download punkt_tab (no model calls)")
    execute = sub.add_parser("run", help="Start a small paid model run (default: one sample)")
    execute.add_argument("--provider", choices=["deepseek", "qwen"], required=True)
    selection = execute.add_mutually_exclusive_group()
    selection.add_argument("--limit", type=int, default=1)
    selection.add_argument("--sample-id", action="append", help="Official key; repeat to select several")
    execute.add_argument("--max-tokens", type=int, default=4096)
    resume = sub.add_parser("resume", help="Resume saved tasks and parameters, skipping successes")
    resume.add_argument("run", type=Path)
    score = sub.add_parser("score", help="Offline scoring; never calls a provider")
    score.add_argument("run", type=Path)
    analysis = sub.add_parser("analyze", help="Descriptive statistics for one or two scored runs")
    analysis.add_argument("runs", type=Path, nargs="+")
    analysis.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    load_dotenv(workspace / ".env", override=False)
    try:
        if args.command == "prepare":
            result = summarize(workspace / "reports")
            if args.download_nltk:
                import nltk
                # Local resource directory keeps setup independent of the user profile.
                if not nltk.download("punkt_tab", download_dir=str(ROOT / ".nltk_data"), raise_on_error=True):
                    raise RuntimeError("NLTK resource download failed")
            official_modules()
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "run":
            rows = load_dataset()
            if args.sample_id:
                ids = set(args.sample_id)
                selected = [r for r in rows if str(r["key"]) in ids]
                if len(selected) != len(ids):
                    raise ValueError("One or more sample IDs do not exist")
            else:
                selected = rows[:args.limit]
            # V1 deliberately exposes only smoke/small-batch requests.
            if not 1 <= len(selected) <= 10 or (not args.sample_id and not 1 <= args.limit <= 10):
                raise ValueError("V1 run accepts 1–10 samples only")
            if args.max_tokens < 1:
                raise ValueError("max-tokens must be positive")
            config = json.loads((SUITE / "config" / f"{args.provider}.json").read_text())
            config["parameters"]["max_tokens"] = args.max_tokens
            # 将 dataset 身份与请求参数一并保存，确保运行可审计、可比较。
            config.update(dataset_sha256=digest(DATA), dataset_source=SOURCE)
            env, default = (("DEEPSEEK_BASE_URL", "https://api.deepseek.com") if args.provider == "deepseek"
                            else ("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
            config["base_url"] = os.environ.get(env) or default
            provider = provider_for(config)
            manager = RunManager.create(workspace / "runs", config, tasks_from_rows(selected))
            print(f"Run: {manager.path}", flush=True)
            result = run(manager, provider)
            print(json.dumps({"success": sum(r["status"] == "success" for r in result), "total": len(result)}))
            if any(r["status"] != "success" for r in result):
                return 1
        elif args.command == "resume":
            manager = RunManager(args.run)
            result = run(manager, provider_for(manager.config))
            print(json.dumps({"success": sum(r["status"] == "success" for r in result), "total": len(result)}))
            if any(r["status"] != "success" for r in result):
                return 1
        elif args.command == "score":
            rows = grade_run(RunManager(args.run))
            print(json.dumps({"scored": sum(r["grade_status"] == "scored" for r in rows),
                              "grader_errors": sum(r["grade_status"] == "grader_error" for r in rows), "total": len(rows)}))
            if any(r["grade_status"] == "grader_error" for r in rows):
                return 1
        else:
            analyze(args.runs, args.output)
            print(f"Analysis: {args.output.resolve()}")
    except KeyboardInterrupt:
        print("Interrupted. Saved results remain available; use resume to continue.", file=sys.stderr)
        return 130
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
