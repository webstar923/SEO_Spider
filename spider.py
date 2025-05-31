import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from utils import is_valid_url, get_domain, is_external_url
import time
import queue
import threading
import re
from collections import deque
import sqlite3
import os
import tempfile

class Spider:
    def __init__(self, base_url, log_callback=None, max_depth=3, delay=1.0, max_threads=5, crawl_resources=None, timeout=None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "*/*",
        }
        self.base_url = base_url
        self.base_domain = get_domain(base_url)
        self.log = log_callback or (lambda msg: None)
        
        # Crawling parameters
        self.max_depth = max_depth
        self.delay = delay
        self.max_threads = max_threads
        self.timeout = timeout
        self.start_time = time.time()
        self.error_count = 0
        
        # Thread control
        self.paused = threading.Event()
        self.cancelled = threading.Event()
        self.threads = []
        self.thread_lock = threading.Lock()
        self.visited_lock = threading.Lock()
        
        # URL tracking
        self.visited = set()
        self.visited_count = 0
        
        # Results handling
        self.results_queue = queue.Queue()
        self.batch_size = 100  # Number of results to batch process
        self.batch_lock = threading.Lock()
        
        # Resource settings - use provided settings without defaults
        self.crawl_resources = crawl_resources or {}
        
        # Resource type extensions
        self.resource_extensions = {
            "images": ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico'],
            "documents": ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf'],
            "stylesheets": ['.css', '.scss', '.sass', '.less'],
            "scripts": ['.js', '.jsx', '.ts', '.tsx', '.coffee'],
            "media": ['.mp3', '.mp4', '.wav', '.ogg', '.webm', '.mov', '.avi', '.flv'],
            "archives": ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2']
        }
        
        # Initialize database
        self.db_path = os.path.join(tempfile.gettempdir(), f"seo_spider_{int(time.time())}.db")
        self._init_database()
        
        # Start batch processor thread
        self.batch_processor = threading.Thread(target=self._process_batches, daemon=True)
        self.batch_processor.start()
        
        # Queue for URLs to crawl
        self.url_queue = queue.PriorityQueue()
        self.domain_last_request = {}
        
        # Track robots.txt rules
        self.robots_rules = {}
        self._load_robots_txt()
        
        # Add the base URL to the queue with highest priority (depth 0)
        self.url_queue.put((0, self.base_url, "root"))
        
        # Log resource settings
        self.log(f"Resource settings: {self.crawl_resources}")
    
    def _init_database(self):
        """Initialize SQLite database for storing results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                url TEXT PRIMARY KEY,
                status INTEGER,
                referrer TEXT,
                type TEXT,
                domain TEXT,
                depth INTEGER
            )
        ''')
        conn.commit()
        conn.close()
    
    def _cleanup(self):
        """Clean up resources"""
        # Close all database connections first
        try:
            conn = self._get_db_connection()
            conn.close()
        except:
            pass
        
        # Wait a bit to ensure all connections are closed
        time.sleep(1)
        
        # Try to delete the database file
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
                    break
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retrying
                else:
                    self.log(f"Error during cleanup after {max_retries} attempts: {str(e)}")
    
    def _load_robots_txt(self):
        """Load robots.txt rules for the base domain"""
        try:
            robots_url = f"https://{self.base_domain}/robots.txt"
            response = requests.get(robots_url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                # Simple parsing of robots.txt
                user_agent = None
                for line in response.text.splitlines():
                    line = line.strip().lower()
                    if line.startswith("user-agent:"):
                        user_agent = line[11:].strip()
                    elif line.startswith("disallow:") and user_agent in ["*", "seo-spider"]:
                        path = line[9:].strip()
                        if path:
                            self.robots_rules[path] = True
        except Exception as e:
            self.log(f"Error loading robots.txt: {str(e)}")
    
    def _is_allowed_by_robots(self, url):
        """Check if URL is allowed by robots.txt rules"""
        parsed = urlparse(url)
        path = parsed.path
        
        for rule in self.robots_rules:
            if path.startswith(rule):
                return False
        return True
    
    def _respect_rate_limit(self, domain):
        """Implement rate limiting per domain"""
        current_time = time.time()
        if domain in self.domain_last_request:
            elapsed = current_time - self.domain_last_request[domain]
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
        
        self.domain_last_request[domain] = time.time()
    
    def _is_resource_url(self, url):
        """Check if a URL is a resource based on its extension"""
        # Remove query parameters and fragments
        url = url.split('?')[0].split('#')[0]
        url_lower = url.lower()
        
        for resource_type, extensions in self.resource_extensions.items():
            if self.crawl_resources.get(resource_type, False):  # Only check enabled resource types
                if any(url_lower.endswith(ext) for ext in extensions):
                    return True
        return False
    
    def _normalize_url(self, url):
        """Normalize URL to prevent duplicates"""
        # Remove trailing slash
        url = url.rstrip('/')
        
        # Remove URL fragments
        url = url.split('#')[0]
        
        # Convert to lowercase
        url = url.lower()
        
        return url
    
    def _extract_links(self, url, html_content):
        """Extract all links from HTML content"""
        links = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        for tag in soup.find_all(['a', 'img', 'script', 'link']):
            href = tag.get('href') or tag.get('src')
            if not href:
                continue
                
            if href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                continue
                
            if tag.get('rel') and 'nofollow' in [r.lower() for r in tag.get('rel')]:
                continue
                
            full_url = urljoin(url, href)
            if is_valid_url(full_url):
                # Normalize URL
                normalized_url = self._normalize_url(full_url)
                
                # Check if URL is already in queue or visited
                if normalized_url not in self.visited:
                    # Check if this is a resource URL
                    resource_type = self._get_resource_type(normalized_url)
                    if resource_type:
                        # Only add resource URLs if their type is enabled
                        if self.crawl_resources.get(resource_type, False):
                            links.append(normalized_url)
                            self.log(f"Adding resource URL ({resource_type}): {normalized_url}")
                    else:
                        # Always add non-resource URLs
                        links.append(normalized_url)
        
        return links
    
    def _get_resource_type(self, url):
        """Get the resource type of a URL"""
        # Remove query parameters and fragments
        url = url.split('?')[0].split('#')[0]
        url_lower = url.lower()
        
        for resource_type, extensions in self.resource_extensions.items():
            if any(url_lower.endswith(ext) for ext in extensions):
                return resource_type
        return None
    
    def _get_db_connection(self):
        """Get a new database connection for the current thread"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)  # Add timeout
            conn.execute("PRAGMA busy_timeout = 30000")  # Set busy timeout
            return conn
        except Exception as e:
            self.log(f"Error creating database connection: {str(e)}")
            raise
    
    def _process_batches(self):
        """Process results in batches and write to SQLite"""
        batch = []
        while not self.cancelled.is_set():
            try:
                # Get result from queue with timeout
                result = self.results_queue.get(timeout=1.0)
                batch.append(result)
                
                # Process batch if it reaches the batch size
                if len(batch) >= self.batch_size:
                    self._write_batch_to_db(batch)
                    batch = []
                    
            except queue.Empty:
                # If queue is empty but we have a partial batch, process it
                if batch:
                    self._write_batch_to_db(batch)
                    batch = []
                continue
            except Exception as e:
                self.log(f"Error in batch processor: {str(e)}")
                continue
        
        # Process any remaining results
        if batch:
            self._write_batch_to_db(batch)
        
        # Ensure all results are written to database
        self.log("Batch processor finished processing all results")
        
        # Wait a bit to ensure all database operations are complete
        time.sleep(1)
    
    def _write_batch_to_db(self, batch):
        """Write a batch of results to the database"""
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT OR REPLACE INTO results (url, status, referrer, type, domain, depth)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', [(r['url'], r['status'], r['referrer'], r['type'], r['domain'], r['depth']) for r in batch])
            conn.commit()
            self.log(f"Stored {len(batch)} results in database")
        except Exception as e:
            self.log(f"Error writing batch to database: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def _crawl_url(self, url, depth, referrer):
        """Crawl a single URL and add discovered links to the queue"""
        if self.cancelled.is_set():
            return
            
        while self.paused.is_set():
            if self.cancelled.is_set():
                return
            time.sleep(0.1)
            
        domain = get_domain(url)
        self._respect_rate_limit(domain)
        
        self.log(f"検査中: {url} (深さ: {depth})")
        
        # Retry logic
        max_retries = 3
        retry_delay = 1.0
        response = None
        status = "Request Failed"
        content_type = ""
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=60)
                status = response.status_code
                content_type = response.headers.get('Content-Type', '')
                break
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    self.log(f"Retry {attempt + 1}/{max_retries} for {url}: {str(e)}")
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    self.log(f"Error crawling {url} after {max_retries} attempts: {str(e)}")
                    self.error_count += 1
        
        url_type = "external" if is_external_url(self.base_domain, url) else "internal"
        
        # Store result in queue
        result = {
            'url': url,
            'status': status,
            'referrer': referrer,
            'type': url_type,
            'domain': domain,
            'depth': depth
        }
        self.results_queue.put(result)
        
        # Only follow links if it's an internal page and we haven't reached max depth
        if url_type == "internal" and status == 200 and 'text/html' in content_type and depth < self.max_depth:
            if response and response.text:
                try:
                    links = self._extract_links(url, response.text)
                    for link in links:
                        if link not in self.visited and self._is_allowed_by_robots(link):
                            self.url_queue.put((depth + 1, link, url))
                except Exception as e:
                    self.log(f"Error extracting links from {url}: {str(e)}")
                    self.error_count += 1
    
    def _check_timeout(self):
        """Check if the global timeout has been reached"""
        if self.timeout and time.time() - self.start_time > self.timeout:
            self.log("Global timeout reached. Stopping crawl.")
            self.cancel()
            return True
        return False
    
    def _worker(self):
        """Worker thread function to process URLs from the queue"""
        while not self.cancelled.is_set():
            if self._check_timeout():
                break
                
            try:
                # Get URL from queue with timeout to allow checking cancelled flag
                depth, url, referrer = self.url_queue.get(timeout=1)
                
                # Skip if already visited
                with self.visited_lock:
                    if url in self.visited:
                        self.url_queue.task_done()
                        continue
                    self.visited.add(url)
                    self.visited_count += 1
                    
                # Crawl the URL
                self._crawl_url(url, depth, referrer)
                
                self.url_queue.task_done()
                
                # Log progress periodically
                if self.visited_count % 10 == 0:  # Log every 10 URLs
                    self.log(f"進捗: {self.visited_count} 件を検査中...")
                
            except queue.Empty:
                # Queue is empty, check if we should exit
                if self.url_queue.empty() and not self.paused.is_set():
                    # Double check if any other thread might add more URLs
                    time.sleep(1)  # Give other threads a chance to add URLs
                    if self.url_queue.empty() and not self.paused.is_set():
                        break
            except Exception as e:
                self.log(f"Error in worker thread: {str(e)}")
                self.error_count += 1
        
        # Log thread completion
        self.log(f"スレッドが完了しました。検査済み: {self.visited_count} 件")
    
    def crawl(self, url=None):
        """Start the crawling process"""
        if url:
            self.url_queue = queue.PriorityQueue()
            self.url_queue.put((0, url, "root"))
            self.visited.clear()
            
            # Clear results table using thread-local connection
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM results")
            conn.commit()
            conn.close()
        
        # Start worker threads
        with self.thread_lock:
            self.threads = []
            # Always start max_threads number of threads, regardless of initial queue size
            for _ in range(self.max_threads):
                thread = threading.Thread(target=self._worker, daemon=True)
                thread.start()
                self.threads.append(thread)
            
            # Log initial status
            self.log(f"クロールを開始しました。最大深度: {self.max_depth}, スレッド数: {self.max_threads}")
            
            # Don't wait for threads to complete here
            # Let the main thread continue while workers run in background
    
    def pause(self):
        """Pause the crawling process"""
        if not self.cancelled.is_set():
            self.paused.set()
            self.log("一時停止しました。")
        else:
            self.log("キャンセルされたため、一時停止できません。")
    
    def resume(self):
        """Resume the crawling process"""
        if not self.cancelled.is_set():
            self.paused.clear()
            self.log("再開しました。")
            
            # Restart worker threads if needed
            with self.thread_lock:
                active_threads = sum(1 for t in self.threads if t.is_alive())
                if active_threads == 0 and not self.url_queue.empty():
                    self.threads = []
                    for _ in range(min(self.max_threads, self.url_queue.qsize())):
                        thread = threading.Thread(target=self._worker, daemon=True)
                        thread.start()
                        self.threads.append(thread)
        else:
            self.log("キャンセルされたため、再開できません。")
    
    def cancel(self):
        """Cancel the crawling process"""
        self.cancelled.set()
        self.paused.clear()  # Ensure threads can exit
        
        # Wait for threads to finish
        with self.thread_lock:
            for thread in self.threads:
                if thread.is_alive():
                    thread.join(timeout=1.0)
        
        # Wait for batch processor to finish
        if self.batch_processor.is_alive():
            self.batch_processor.join(timeout=2.0)
        
        # Get results from database before cleanup
        results = []
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM results")
            rows = cursor.fetchall()
            for row in rows:
                results.append({
                    'url': row[0],
                    'status': row[1],
                    'referrer': row[2],
                    'type': row[3],
                    'domain': row[4],
                    'depth': row[5]
                })
            conn.close()
            self.log(f"Retrieved {len(results)} results from database before cleanup")
        except Exception as e:
            self.log(f"Error getting results from database: {str(e)}")
        
        # Don't delete the database here - let the main thread handle cleanup
        self.log("キャンセルされました。")
        return results
    
    def get_results(self):
        """Get all results from the database"""
        # Wait for batch processor to finish
        if self.batch_processor.is_alive():
            self.batch_processor.join(timeout=5.0)
        
        results = []
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM results")
            rows = cursor.fetchall()
            for row in rows:
                results.append({
                    'url': row[0],
                    'status': row[1],
                    'referrer': row[2],
                    'type': row[3],
                    'domain': row[4],
                    'depth': row[5]
                })
            self.log(f"Retrieved {len(results)} results from database")
        except Exception as e:
            self.log(f"Error getting results from database: {str(e)}")
        finally:
            if conn:
                conn.close()
        return results
