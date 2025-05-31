# SEO Spider

A professional web crawler inspired by Screaming Frog SEO Spider, designed to analyze websites for broken links and WHOIS information.

## Features

- **Modern Crawling Architecture**: Uses a queue-based approach instead of recursion for better scalability and control
- **Multi-threaded Crawling**: Crawls multiple pages simultaneously for faster results
- **Depth Management**: Controls how deep the crawler goes from the start page
- **Rate Limiting**: Respects server resources by adding delays between requests
- **Robots.txt Compliance**: Respects robots.txt rules to be a good web citizen
- **WHOIS Information**: Retrieves domain registration information for external links
- **Broken Link Detection**: Identifies and reports broken links (HTTP 4xx and 5xx errors)
- **Export to Excel**: Exports results to Excel for further analysis
- **Pause/Resume/Cancel**: Full control over the crawling process

## Requirements

- Python 3.8+
- Dependencies listed in requirements.txt

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python main.py
   ```

2. Select a website from the dropdown or enter a custom URL
3. Enter your WHOIS API key (from api-ninjas.com)
4. Click "検査開始" (Start Scan) to begin crawling
5. Use the pause/resume/cancel buttons to control the crawling process
6. Export results to Excel when finished

## Configuration

The crawler can be configured with the following parameters in the Spider class:

- `max_depth`: Maximum depth to crawl (default: 3)
- `delay`: Delay between requests to the same domain in seconds (default: 0.5)
- `max_threads`: Maximum number of concurrent threads (default: 5)

## How It Works

1. The crawler starts with the base URL and adds it to a priority queue
2. Worker threads pull URLs from the queue and crawl them
3. For each page, the crawler:
   - Checks if the URL is allowed by robots.txt
   - Respects rate limiting per domain
   - Extracts all links from the page
   - Adds new links to the queue with increased depth
   - Records the page status and WHOIS information
4. Results are displayed in the UI and can be exported to Excel

## License

MIT 