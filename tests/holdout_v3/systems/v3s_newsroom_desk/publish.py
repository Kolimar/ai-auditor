import sys

from desk import fact_check_draft, generate_headlines
from wire import build_markdown_digest, extract_story_metadata, summarize_wire_story, verify_article_record


def run(path: str):
    raw_items = open(path).read().split("<!--item-->")
    stories = []
    for raw in raw_items:
        meta = extract_story_metadata(raw)
        stories.append({**meta, "summary": summarize_wire_story(raw)})
    ready = [s for s in stories if verify_article_record(s)]
    print(build_markdown_digest(ready))


if __name__ == "__main__":
    run(sys.argv[1])
