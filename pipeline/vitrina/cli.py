"""Команды: voices, script, build, run, publish, demo."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import assemble, config, llm, publish, stt, subtitles, tts, visuals
from .ledger import Ledger


def _ledger(cfg: dict) -> Ledger:
    return Ledger(cfg["project"]["products_csv"])


def cmd_voices(cfg, args):
    vs = tts.VoiceStudio(cfg["tts"]["base_url"], cfg["tts"].get("api_key", ""))
    if not vs.health():
        sys.exit(f"VoiceStudio не отвечает на {cfg['tts']['base_url']}")
    for v in vs.voices():
        if isinstance(v, dict):
            print(f"{v.get('id') or v.get('voice_id') or v.get('name')}\t{v.get('name', '')}\t{v.get('language', v.get('engine', ''))}")
        else:
            print(v)


def do_script(cfg, ledger: Ledger, pid: str, pick: int | None = None) -> dict:
    product = ledger.get(pid)
    out = config.out_dir(cfg, pid)
    variants = llm.generate_scripts(cfg, product)
    (out / "script_variants.json").write_text(json.dumps(variants, ensure_ascii=False, indent=2), encoding="utf-8")
    chosen = variants[(pick or 1) - 1] if pick else variants[0]
    (out / "script.json").write_text(json.dumps(chosen, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "script.txt").write_text(llm.script_to_text(chosen), encoding="utf-8")
    ledger.update(pid, status="scripted", script_path=str(out / "script.json"))
    print(f"[{pid}] сценарий: {len(variants)} вариант(ов), выбран {pick or 1}")
    print("   " + llm.script_to_text(chosen))
    return chosen


def do_build(cfg, ledger: Ledger, pid: str) -> Path:
    product = ledger.get(pid)
    out = config.out_dir(cfg, pid)
    script_path = out / "script.json"
    if not script_path.exists():
        do_script(cfg, ledger, pid)
    script = json.loads(script_path.read_text(encoding="utf-8"))
    text = llm.script_to_text(script)

    voice = tts.synthesize(cfg, text, product["channel"], out / "voice.wav")
    words = stt.word_timings(cfg, voice, text)
    (out / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    ass = subtitles.build_ass(cfg, words, out / "subs.ass")

    frames = visuals.prepare_images(cfg, product, Ledger.images_of(product), out / "frames")
    work = out / "work"
    work.mkdir(exist_ok=True)
    video = assemble.build_video(cfg, frames, voice, ass, work, out / f"{pid}.mp4")
    cover = visuals.make_cover(cfg, frames[0], script.get("cover_title") or product["title"], out / f"{pid}_cover.png")
    ledger.update(pid, status="built", video_path=str(video), cover_path=str(cover))
    print(f"[{pid}] готово: {video}")
    return video


def cmd_script(cfg, args):
    do_script(cfg, _ledger(cfg), args.id, args.pick)


def cmd_build(cfg, args):
    do_build(cfg, _ledger(cfg), args.id)


def cmd_run(cfg, args):
    ledger = _ledger(cfg)
    todo = ledger.items(status="new", channel=args.channel) + ledger.items(status="scripted", channel=args.channel)
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("Нет товаров со статусом new или scripted")
        return
    for row in todo:
        try:
            do_build(cfg, ledger, row["id"])
        except Exception as e:
            print(f"[{row['id']}] ОШИБКА: {e}")
            ledger.update(row["id"], notes=f"ошибка: {str(e)[:200]}")


def cmd_publish(cfg, args):
    ledger = _ledger(cfg)
    product = ledger.get(args.id)
    out = config.out_dir(cfg, args.id)
    script = json.loads((out / "script.json").read_text(encoding="utf-8"))
    video = Path(product["video_path"])
    res = publish.telegram_video(cfg, video, publish.caption_for(product, script))
    ledger.update(args.id, status="published", published_at=dt.datetime.now().isoformat(timespec="minutes"))
    print(f"[{args.id}] опубликовано в Telegram, message_id={res.get('result', {}).get('message_id')}")


def cmd_demo(cfg, args):
    """Полная проверка установки без нейросетей: тестовый товар, картинка, тишина вместо голоса."""
    cfg = json.loads(json.dumps(cfg))
    cfg["tts"]["provider"] = "mock"
    cfg["llm"]["provider"] = "none"
    cfg["stt"]["provider"] = "none"
    data = Path(cfg["project"]["data_dir"])
    cfg["project"]["products_csv"] = str(data / "demo_products.csv")
    ledger = Ledger(cfg["project"]["products_csv"])
    pid = "demo-001"
    img = data / "images" / "demo.png"
    visuals.placeholder("Тестовый товар", img, 1200, 900)
    if not any(r["id"] == pid for r in ledger.rows):
        ledger.add(id=pid, channel="dom", title="Складной силиконовый дуршлаг",
                   description="Складывается до двух сантиметров. Выдерживает кипяток. Моется в посудомойке.",
                   price=490, affiliate_url="https://example.com", images=str(img), category="Дом")
    video = do_build(cfg, ledger, pid)
    print(f"Демо собрано: {video}\nЕсли файл открывается и в нём есть субтитры и наезд на картинку, установка в порядке.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="vitrina", description="Пайплайн коротких товарных роликов")
    p.add_argument("--config", help="путь к config.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("voices", help="список голосов VoiceStudio").set_defaults(fn=cmd_voices)
    s = sub.add_parser("script", help="сгенерировать сценарий для товара")
    s.add_argument("id")
    s.add_argument("--pick", type=int, help="номер варианта")
    s.set_defaults(fn=cmd_script)
    b = sub.add_parser("build", help="собрать ролик для товара")
    b.add_argument("id")
    b.set_defaults(fn=cmd_build)
    r = sub.add_parser("run", help="собрать все новые товары")
    r.add_argument("--channel")
    r.add_argument("--limit", type=int)
    r.set_defaults(fn=cmd_run)
    pub = sub.add_parser("publish", help="опубликовать ролик в Telegram-витрину")
    pub.add_argument("id")
    pub.set_defaults(fn=cmd_publish)
    sub.add_parser("demo", help="проверка установки без нейросетей").set_defaults(fn=cmd_demo)

    args = p.parse_args(argv)
    cfg = config.load(args.config)
    args.fn(cfg, args)
