from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT='https://publications.europa.eu/webapi/rdf/sparql'
SCHEME='http://data.europa.eu/6p8/low2015/scheme'

queries=[
('count',f'''PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT (COUNT(DISTINCT ?c) AS ?count)
WHERE {{ ?c skos:inScheme <{SCHEME}> . }}'''),
('sample',f'''PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?c ?notation ?label
WHERE {{
  ?c skos:inScheme <{SCHEME}> .
  OPTIONAL {{ ?c skos:notation ?notation . }}
  OPTIONAL {{ ?c skos:prefLabel ?label . FILTER(lang(?label)='it') }}
}}
ORDER BY ?notation
LIMIT 20'''),
('predicates',f'''PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?p
WHERE {{ ?c skos:inScheme <{SCHEME}> ; ?p ?o . }}
ORDER BY ?p'''),
]

for name,query in queries:
    qs=urlencode({'query':query,'format':'text/csv'})
    req=Request(ENDPOINT+'?'+qs,headers={'User-Agent':'partite-mozzanica-build/1.0','Accept':'text/csv'})
    with urlopen(req,timeout=60) as r:
        body=r.read().decode('utf-8','replace')
    print('\n### '+name+' ###')
    print(body[:20000])
