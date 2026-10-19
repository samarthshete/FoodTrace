#!/bin/bash
# Pre-load the demo products into the API's response cache (spec 025).
B=${API_URL:-http://localhost:8000}
for g in 0096619160754 0076808008470 0857484006284 0744473476138 0037600138727 0038000138416 0028400090858 0016000275287 \
         0681131276344 0078742147970 0044700019887 0894263002020 0021000010615 5449000054227 \
         6111035000430 0096619555505 3228857001491 5016935000713 3017620422003 0098765432105 0000042104964; do
  for p in "" /breakdown /alternatives /recalls; do
    curl -s -o /dev/null -w "%{http_code} %{time_total}s $g$p\n" "$B/products/$g$p"
  done
done
for c in "" /breakfast /yogurts /breads /snacks /bars /sweets /drinks /cheese /meals /spreads; do
  curl -s -o /dev/null -w "%{http_code} %{time_total}s explore$c\n" "$B/explore$c?per_category=4"
  curl -s -o /dev/null "$B/explore$c?limit=48"
done
curl -s -o /dev/null "$B/explore?per_category=4"; curl -s -o /dev/null "$B/methodology"

# The assistant's searches (as the keyword parser writes them), and each top result.
W=${WEB_URL:-http://localhost:3000}
for q in pringles "pringles original" spam "spam classic" "reeses peanut butter cups" "reeses cups" cheerios \
         chocolate "hersheys milk chocolate" "lays classic potato chips" "lays classic chips" oreo coke \
         "coca cola" nutella "kind bar" "greek yogurt" "peanut butter" doritos; do
  gtin=$(curl -s "$W/api/search?q=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$q")" \
    | python3 -c 'import json,sys;d=json.load(sys.stdin);r=d.get("results") or [];print(d.get("gtin") or (r[0]["gtin"] if r else ""))')
  [ -n "$gtin" ] && curl -s -o /dev/null "$B/products/$gtin"
  echo "search \"$q\" -> ${gtin:-none}"
done
