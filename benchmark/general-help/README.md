# Scripts for Creating Benchmark Datasets and Evaluation 

## General Help Dataset

This dataset is used in Quality Assurance of our deployed portal chatbot, following rigorous best practices... TODO: explain more here.

### Get content from NF docs with crawler

This contains a Scrapy spider that crawls all pages under the [public NF help docs](https://help.nf.synapse.org/NFdocs/) section and converts each page into a Markdown document. The Markdown files are saved in an output directory for further use (but not included in this repository). This is used for creating the evaluation dataset.

#### Overview

The spider starts at the base URL (`https://help.nf.synapse.org/NFdocs/`), follows all internal links within the NFdocs section, converts the HTML content of each page to Markdown using the [`markdownify`](https://github.com/matthewwithanm/python-markdownify) library, and saves the output as individual Markdown files.

#### Requirements

- Python 3.x
- [Scrapy](https://scrapy.org/)
- [markdownify](https://github.com/matthewwithanm/python-markdownify)

#### Run crawler

```
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
pip install scrapy markdownify
scrapy runspider nfdocs_spider.py
```

Now check that a directory `output_markdown` has been created locally and contains the Markdown files (again, these are git-ignored).

#### Create synthetic dataset with LLM

TODO:
- Explain dataset structure and associated prompt/schema here
- Explain batch API usage here (including OpenAI model used)
- Explain human validation of synthetic dataset
