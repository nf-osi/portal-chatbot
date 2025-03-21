import os
import scrapy
from markdownify import markdownify as md

class NFDocsSpider(scrapy.Spider):
    name = "nfdocs"
    allowed_domains = ["help.nf.synapse.org"]
    start_urls = ["https://help.nf.synapse.org/NFdocs/"]

    def parse(self, response):
        # Extract the title from the page and clean it up.
        title = response.xpath('//title/text()').get()
        if title:
            title = title.strip().replace(" ", "_")
        else:
            title = "untitled_page"

        # Extract the main HTML content.
        content_html = response.xpath('//body').get()
        if content_html:
            markdown_content = md(content_html)
            # Prepend the source page URL as metadata.
            markdown_with_url = f"source_page_url: {response.url}\n\n{markdown_content}"
            # Ensure the output directory exists.
            output_dir = "output_markdown"
            os.makedirs(output_dir, exist_ok=True)
            filename = f"{title}.md"
            file_path = os.path.join(output_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_with_url)
            self.log(f"Saved file: {file_path}")

        # Follow all internal links under /NFdocs/.
        for href in response.css("a::attr(href)").getall():
            next_page = response.urljoin(href)
            if next_page.startswith("https://help.nf.synapse.org/NFdocs/"):
                yield scrapy.Request(next_page, callback=self.parse)
