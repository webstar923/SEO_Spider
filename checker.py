from whois_checker import WhoisChecker

whois_checker = WhoisChecker()
domain = 'https://www.caa.go.jp'
whois = whois_checker.check_domain(domain)
print("whois", whois, "ddd")