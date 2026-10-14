from curl_cffi import requests

url = 'https://haveibeenpwned.com/unifiedsearch/vkhai2603%40gmail.com'

# Giữ nguyên toàn bộ Header và Cookie từ curl của bạn
headers = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9,vi;q=0.8,fr-FR;q=0.7,fr;q=0.6,zh-CN;q=0.5,zh;q=0.4',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://haveibeenpwned.com/',
    'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36',
}

cookies = {
    'cf_clearance': 'fxqCVGTpQsA060GSwYnfZxRCRT4oY0F3NwNSk.sDt10-1779859309-1.2.1.1-HiXQE0FN_wnB0368c.cwJLJ5soOUX8g5ePSiY4_jyqxAJJpso_sAvlqlAqk8hnZHdgkETrnt7XALbAV9uS3wyP_ZUuSemSo0a4IOHJTTqoJT_CifToB8nB.dyVDHsfcKLLuI6LqHFV61BGDYKd4qPLTI27bt51Tq86LKwqgQl.02W2SRrZ63m_JPOGsidAg698BBKpl5A8XjHGjutwvlepRZSjdqblxADLgLceLlpzldJ5MDd9ZXZ8ZI9zZbSu1JXLtQP..nG2oBRRwcXpjAHo5WvdtZ8lnNt42LYoGDRiOLMHda8AhxVXg9AiAgOeF3ghXDOlJH10g3hxKQlel9XA',
    '__cf_bm': 'H9GvQt9JNeakxTLsEdbrqa45pCqslnzSte4aiCEYRCs-1779938442.5659077-1.0.1.1-NQYaJ68ByRXkQoujgZBQ5BJcsfblpSfUO5OmD7r_vAgXNvRcJ2eh86FeVgEwzTAkmGVZXuwDr8uPZJq2V7M.ylKXrbiDar3Z1ejXvwEle3R6dgblNPrc074bocCdLROM'
}

response = requests.get(
    url, 
    headers=headers, 
    cookies=cookies, 
    impersonate="chrome110"  # Hoặc "chrome120" để giả lập Chrome bản mới
)

print(f"Status Code: {response.status_code}")
print(response.text)