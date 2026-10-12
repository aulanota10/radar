"""Amostra das filas simuladas de 13/10 a 02/11/2026 (leitor e base corrigidos em 12/10).
Cada linha de data distinta (concurso + texto) entra uma vez, com a primeira fila em que aparece, o destinatário
e a fonte da mensagem. Estratos: semana da primeira aparição (60/50/40), no máximo 3 por concurso em cada semana,
e no mínimo 20 linhas de presença obrigatória (instalação, portões, comparecimento), que são o padrão novo.
Uso: python3 sortear.py PASTA_SIMULACAO AGENDA_JSON SAIDA"""
import glob, json, os, random, re, sys, collections
sim, agenda_f, out = sys.argv[1:4]
nome2slug = {}
for e in json.load(open(agenda_f)):
    nome2slug.setdefault(e["nome"], e["concurso"])
linhas = {}
for f in sorted(glob.glob(os.path.join(sim, "*", "fila-*.md"))):
    dia = re.search(r"fila-(\d{4}-\d\d-\d\d)", f).group(1)
    conc = dest = None
    bloco = []
    for l in open(f, encoding="utf-8"):
        l = l.rstrip("\n")
        if l.startswith("## "):
            conc = l[3:].strip()
        elif l.startswith("**Para:"):
            dest = l.strip("*").replace("Para: ", "")
        elif l == "```" and bloco:
            fonte = next((x for x in bloco if x.startswith("Fonte:")), "")
            for x in bloco:
                if x.startswith("• "):
                    t = re.sub(r"\s*\((faltam \d+ dias|é amanhã|é hoje)\)\s*$", "", x[2:])
                    k = (conc, t)
                    if k not in linhas:
                        linhas[k] = {"concurso": conc, "slug": nome2slug.get(conc), "fila": dia, "destinatario": dest,
                                     "linha": x[2:], "fonte_da_mensagem": fonte}
            bloco = []
        elif l != "```":
            bloco.append(l)
rng = random.Random(20261012)
PRES = re.compile(r"comparec|port[õa]|instala|presen", re.I)
sem = lambda d: 0 if d <= "2026-10-19" else 1 if d <= "2026-10-26" else 2
todos = list(linhas.values())
rng.shuffle(todos)
amostra, usados = [], set()
pres = [x for x in todos if PRES.search(x["linha"])][:20]
for x in pres:
    amostra.append(x); usados.add(id(x))
cota = {0: 60, 1: 50, 2: 40}
cont = collections.Counter((sem(x["fila"]), x["concurso"]) for x in amostra)
n_sem = collections.Counter(sem(x["fila"]) for x in amostra)
for x in todos:
    s = sem(x["fila"])
    if id(x) in usados or n_sem[s] >= cota[s] or cont[(s, x["concurso"])] >= 3:
        continue
    amostra.append(x); usados.add(id(x)); n_sem[s] += 1; cont[(s, x["concurso"])] += 1
for i, x in enumerate(amostra, 1):
    x["id"] = f"s{i:03d}"
json.dump(amostra, open(os.path.join(out, "amostra.json"), "w"), ensure_ascii=False, indent=1)
por = collections.defaultdict(list)
for x in amostra:
    por[x["concurso"]].append(x)
lotes = [[] for _ in range(6)]
for c, v in sorted(por.items(), key=lambda kv: -len(kv[1])):
    min(lotes, key=len).extend(v)
for i, l in enumerate(lotes, 1):
    json.dump(l, open(os.path.join(out, f"lote-{i}.json"), "w"), ensure_ascii=False, indent=1)
print(len(linhas), len(amostra), len(por), [len(l) for l in lotes], sum(1 for x in amostra if PRES.search(x["linha"])), sum(1 for x in amostra if not x["slug"]))
