"""選用:用 CKIP NER 找出沒有關鍵字提示的人名。需 pip install ckip-transformers(會下載模型,首次需連網)。"""
_driver = None


def _load():
    global _driver
    if _driver is None:
        try:
            from ckip_transformers.nlp import CkipNerChunker
        except ImportError:
            raise SystemExit("--ner 需要:pip install ckip-transformers")
        _driver = CkipNerChunker(model="bert-base")
    return _driver


def ner_names(text):
    """回傳文字中被辨識為 PERSON 的詞(去重)。"""
    if not text.strip():
        return []
    result = _load()([text], show_progress=False)[0]
    return sorted({e.word for e in result if e.ner == "PERSON" and len(e.word) >= 2})
