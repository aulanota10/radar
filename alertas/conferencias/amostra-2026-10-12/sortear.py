"""Amostra estratificada da agenda dos alertas para medir a taxa de erro de datas (12/10/2026).

População: eventos vigentes de concursos ativos que ainda podem virar alerta (datados de hoje em
diante, ou relativos/condicionados). Estratos: forma da data × tipo de evento. Os datados recebem
2/3 da amostra porque viram alerta agendado diretamente. Mínimo de 3 por tipo nos datados e 2 nos
não datados; o resto proporcional. Semente fixa para que a amostra possa ser refeita.
Uso: python3 sortear.py AGENDA_JSON VIGIA HOJE SAIDA_DIR
"""
import json, random, sys, os, collections, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import agenda as A

agenda_f, vigia, hoje, saida = sys.argv[1:5]
H = A.D(hoje)
SEMENTE, N_DAT, N_NAO = 20261012, 200, 100
ag = json.load(open(agenda_f))
pop = [e for e in ag if e["situacao"] == "ativo" and e["tipo_evento"] not in ("suspensao", "retomada", "cancelamento")
       and ((e["forma"] in ("fixa", "janela") and (e["fim"] or e["inicio"]) >= hoje) or e["forma"] in ("relativa", "condicionada"))]
conc = A.ler_concursos(vigia)
raw = {(s, ev.get("id")): ev for s, c in conc.items() for ev in c["eventos"] if ev.get("estado") == "vigente"}

def alocar(itens, n, minimo):
    por = collections.defaultdict(list)
    for e in itens:
        por[e["tipo_evento"]].append(e)
    aloc = {t: min(len(v), minimo) for t, v in por.items()}
    resto = n - sum(aloc.values())
    tot = sum(len(v) - aloc[t] for t, v in por.items())
    frac = {t: resto * (len(v) - aloc[t]) / tot for t, v in por.items()}
    for t in por:
        aloc[t] += int(frac[t])
    for t in sorted(por, key=lambda t: -(frac[t] - int(frac[t])))[: n - sum(aloc.values())]:
        aloc[t] += 1
    return por, aloc

rng = random.Random(SEMENTE)
amostra, estratos = [], []
for nome, itens, n, m in (("datada", [e for e in pop if e["forma"] in ("fixa", "janela")], N_DAT, 3),
                          ("nao_datada", [e for e in pop if e["forma"] in ("relativa", "condicionada")], N_NAO, 2)):
    por, aloc = alocar(itens, n, m)
    for t, v in sorted(por.items()):
        k = min(aloc[t], len(v))
        sel = rng.sample(v, k)
        estratos.append({"grupo": nome, "tipo_evento": t, "N": len(v), "n": k, "peso": len(v) / k if k else 0})
        for e in sel:
            r = raw.get((e["concurso"], e["evento_id"])) or {}
            alerta = {"rotulo": A.rotulo(r) if r else e["descricao"], "data": A.texto_data(r.get("data"), H) if r else e["data_texto"],
                      "agendado": e["tipo_evento"] in A.REGRAS and not (r and (A.janela_longa(r) or A.horario_individual(r))),
                      "regra_antecedencia": A.REGRAS.get(e["tipo_evento"])}
            amostra.append({"id": f"{e['concurso']}#{e['evento_id']}", "estrato": f"{nome}/{t}", "peso": len(v) / k,
                            **{x: e[x] for x in ("concurso", "nome", "evento_id", "tipo_evento", "etapa", "fase", "escopo", "descricao", "forma", "inicio", "fim", "hora", "documento", "item", "pagina")},
                            "data_extraida": r.get("data"), "como_o_alerta_leria": alerta})
os.makedirs(saida, exist_ok=True)
json.dump(amostra, open(os.path.join(saida, "amostra.json"), "w"), ensure_ascii=False, indent=1)
json.dump({"hoje": hoje, "semente": SEMENTE, "populacao": len(pop), "estratos": estratos}, open(os.path.join(saida, "estratos.json"), "w"), ensure_ascii=False, indent=1)
print(len(pop), len(amostra), len({a["concurso"] for a in amostra}))
