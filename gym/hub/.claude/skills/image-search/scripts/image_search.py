#!/usr/bin/env python3
"""
Image search and download tool using icrawler.
Searches Google/Bing Images and downloads results to a local directory.

Usage:
    python image_search.py "gmail UI dashboard" ./output_dir
    python image_search.py "slack interface screenshot" ./output_dir --max 10
    python image_search.py "notion app dark mode" ./output_dir --max 5 --engine bing
"""

import argparse
import os
import sys
import json
from pathlib import Path


def search_and_download(query, output_dir, max_num=8, engine="google", min_size=(400, 300)):
    """Search for images and download them to output_dir."""
    os.makedirs(output_dir, exist_ok=True)

    storage = {"root_dir": output_dir}
    filters = {
        "type": "photo",
        "size": "large",
    }

    results = {"query": query, "engine": engine, "output_dir": str(output_dir), "downloaded": 0, "files": []}

    try:
        if engine == "google":
            from icrawler.builtin import GoogleImageCrawler
            crawler = GoogleImageCrawler(
                feeder_threads=1,
                parser_threads=1,
                downloader_threads=4,
                storage=storage,
            )
            crawler.crawl(
                keyword=query,
                filters=filters,
                max_num=max_num,
                min_size=min_size,
            )
        elif engine == "bing":
            from icrawler.builtin import BingImageCrawler
            crawler = BingImageCrawler(
                feeder_threads=1,
                parser_threads=1,
                downloader_threads=4,
                storage=storage,
            )
            crawler.crawl(
                keyword=query,
                filters=filters,
                max_num=max_num,
                min_size=min_size,
            )
        else:
            print(f"ERROR: Unknown engine '{engine}'. Use 'google' or 'bing'.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"WARNING: {engine} crawler failed: {e}", file=sys.stderr)
        # Fallback to the other engine
        fallback = "bing" if engine == "google" else "google"
        print(f"Falling back to {fallback}...", file=sys.stderr)
        try:
            return search_and_download(query, output_dir, max_num, fallback, min_size)
        except Exception as e2:
            print(f"ERROR: Fallback also failed: {e2}", file=sys.stderr)

    # Count downloaded files
    downloaded_files = sorted(Path(output_dir).glob("*"))
    image_files = [f for f in downloaded_files if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")]
    results["downloaded"] = len(image_files)
    results["files"] = [str(f.name) for f in image_files]

    return results


def multi_search(queries, output_dir, max_per_query=5, engine="google"):
    """Run multiple search queries, saving to subdirectories or with prefixes."""
    all_results = []
    for i, query in enumerate(queries):
        print(f"\n[{i+1}/{len(queries)}] Searching: {query}")
        result = search_and_download(query, output_dir, max_per_query, engine)
        all_results.append(result)
        print(f"  Downloaded {result['downloaded']} images")
    return all_results


def main():
    parser = argparse.ArgumentParser(description="Search and download images from Google/Bing")
    parser.add_argument("query", help="Search query (e.g., 'gmail UI dashboard screenshot')")
    parser.add_argument("output_dir", help="Directory to save images to")
    parser.add_argument("--max", type=int, default=8, help="Max images to download (default: 8)")
    parser.add_argument("--engine", choices=["google", "bing"], default="bing", help="Search engine (default: bing)")
    parser.add_argument("--min-width", type=int, default=400, help="Minimum image width (default: 400)")
    parser.add_argument("--min-height", type=int, default=300, help="Minimum image height (default: 300)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    results = search_and_download(
        query=args.query,
        output_dir=args.output_dir,
        max_num=args.max,
        engine=args.engine,
        min_size=(args.min_width, args.min_height),
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\nDone: {results['downloaded']} images saved to {results['output_dir']}")
        for f in results["files"]:
            print(f"  {f}")


if __name__ == "__main__":
    main()
