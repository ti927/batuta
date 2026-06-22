"""Testes do vigia dos instrumentos de imagem (diagnostico_imagem).

Prova: monta o registro certo (inclusive a contagem de imagens ANEXADAS com bytes),
salva como JSON de nome fixo por instrumento, e é BEST-EFFORT (nunca propaga erro,
para não derrubar o instrumento)."""

import json

import diagnostico_imagem as di


def test_registrar_monta_dict_e_salva_json(monkeypatch):
    capt = {}

    def fake_salvar(nome, conteudo, content_type="application/octet-stream"):
        capt.update(nome=nome, conteudo=conteudo, content_type=content_type)
        return f"https://x/storage/v1/object/public/arquivos/{nome}"

    monkeypatch.setattr(di.arquivos, "salvar", fake_salvar)
    url = di.registrar(
        "montar_imagem",
        "https://api.openai.com/v1/images/edits",
        "POST multipart/form-data",
        {"model": "gpt-image-1.5", "size": "1024x1536", "input_fidelity": "high"},
        [
            {"origem_url": "http://x/a.png", "bytes_anexados": 1234, "enviado_como": "anexo (multipart image[])"},
            {"origem_url": "http://x/b.png", "bytes_anexados": 5678, "enviado_como": "anexo (multipart image[])"},
        ],
    )
    assert capt["nome"] == "diagnostico-montar_imagem.json"
    assert capt["content_type"] == "application/json"
    reg = json.loads(capt["conteudo"].decode("utf-8"))
    assert reg["instrumento"] == "montar_imagem"
    assert reg["endpoint"].endswith("/images/edits")
    assert reg["total_imagens_anexadas"] == 2  # as duas têm bytes → anexadas
    assert reg["imagens_de_entrada"][0]["bytes_anexados"] == 1234
    assert reg["campos"]["input_fidelity"] == "high"
    assert url.endswith("diagnostico-montar_imagem.json")


def test_registrar_texto_para_imagem_zero_anexos(monkeypatch):
    capt = {}
    monkeypatch.setattr(
        di.arquivos, "salvar",
        lambda nome, conteudo, content_type="": capt.update(conteudo=conteudo) or "u",
    )
    di.registrar("gerar_imagem", "u", "POST application/json", {"model": "gpt-image-1"}, [])
    reg = json.loads(capt["conteudo"].decode("utf-8"))
    assert reg["total_imagens_anexadas"] == 0
    assert reg["imagens_de_entrada"] == []


def test_registrar_e_best_effort(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("storage caiu")

    monkeypatch.setattr(di.arquivos, "salvar", boom)
    # NUNCA propaga: devolve None em vez de derrubar o instrumento.
    assert di.registrar("montar_imagem", "u", "m", {}, []) is None
