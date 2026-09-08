"""こよみアラーム の起動口。

Windows では拡張子 .pyw が pythonw.exe に結び付いていて、
これで始めると黒い窓が出ない。ふだんはこちらで開く。

    pythonw run.pyw     窓を出さずに始める
    python  run.pyw     コンソールを付けて始める（不具合を追うとき）

pythonw.exe には標準出力も標準エラーも無い。そのままでは、つまずいても
何も残さずに消えてしまうので、そのときだけ行き場を失った出力を
控えのファイル（%APPDATA%\Koyomi\error.log）へ向け直す。
python.exe で開いたときは何も細工せず、目の前のコンソールに出す。
"""
import datetime as dt
import os
import sys
import traceback
import warnings

# koyomi.APP_NAME と同じ綴り。取り込みでつまずいた場合も控えを残したいので、
# パッケージを読み込む前に要る。ここだけは重複を承知で持っておく。
APP_FOLDER = "Koyomi"
LOG_NAME = "error.log"
LINES = chr(10)                 # お知らせの改行
LOG_LIMIT = 200 * 1024          # これを超えたら古い分は捨てて書き直す

# pythonw で開くと出力先が無い。書き換える前に見分けておく。
HAS_CONSOLE = sys.stderr is not None


def log_path() -> str:
    """控えの置き場所。無ければ作る。"""
    base = os.environ.get("APPDATA")
    if base:
        folder = os.path.join(base, APP_FOLDER)
    else:
        folder = os.path.join(os.path.expanduser("~"), "." + APP_FOLDER.lower())
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, LOG_NAME)


class Journal:
    """書かれたときだけ開いて、すぐ閉じる控え。

    起動のたびに空のファイルを作らないよう、最初の書き込みまで待つ。
    開いたままにすると動かしている間はファイルが掴まれ、
    消すことも移すこともできなくなるので、そのつど開き直す。
    困りごとは滅多に無いから、この手間は問題にならない。
    """

    encoding = "utf-8"

    def __init__(self):
        self._headed = False        # この回の見出しを書いたか
        self._given_up = False      # 書けないと分かったら諦める

    def write(self, text) -> int:
        if not self._given_up:
            try:
                path = log_path()
                if os.path.exists(path) and os.path.getsize(path) > LOG_LIMIT:
                    os.remove(path)         # 古い分は捨てて書き直す
                    self._headed = False
                with open(path, "a", encoding="utf-8") as book:
                    if not self._headed:
                        self._headed = True
                        book.write("\n----- %s -----\n" % dt.datetime.now()
                                   .isoformat(timespec="seconds"))
                    book.write(text)
            except OSError:
                self._given_up = True       # 書けなくても動作そのものは続ける
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def announce(text: str) -> None:
    """人に伝える。

    コンソールがあればそちらへ。無いときは Qt が使えない場面でも出せる、
    素の Windows のお知らせにする。
    """
    if HAS_CONSOLE:
        print(text, file=sys.stderr)
        return
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "こよみアラーム", 0x10)
    except Exception:
        pass


def hush_warnings() -> None:
    """注意書きは控えに混ぜない。

    部品が出す「そのうち無くなります」の類は動作に差し支えない。
    これを控えへ流し込むと毎回ファイルができてしまい、
    「error.log がある＝つまずいた」という目印にならなくなる。
    """
    warnings.showwarning = lambda *args, **kwargs: None


def on_trouble(kind, value, chain) -> None:
    """誰にも捕まえてもらえなかった困りごとの後始末。"""
    sys.stderr.write("".join(traceback.format_exception(kind, value, chain)))
    announce("開始できませんでした。\n\n%s: %s\n\n詳しい記録：\n%s"
             % (kind.__name__, value, log_path()))


def missing_parts(trouble) -> str:
    """部品が足りないときの言い分け。どの Python で開いたかまで伝える。"""
    said = [
        "必要な部品が見つかりません。",
        "",
        str(trouble),
        "",
        "開こうとした Python：",
        sys.executable,
        "",
        "install.bat を実行して入れ直すか、",
        "tools/make_shortcut.py でショートカットを作ってください。",
    ]
    if not HAS_CONSOLE:                 # 目の前に出ないので、置き場所を添える
        said += ["", "詳しい記録：", log_path()]
    return LINES.join(said)


def main() -> int:
    if not HAS_CONSOLE:
        # pythonw で開いた。出力先が無いので、控えのファイルへ向け直す。
        sys.stdout = open(os.devnull, "w")  # 部品どうしの挨拶などは捨てる
        sys.stderr = Journal()              # 困りごとだけ控えに残す
        sys.excepthook = on_trouble
        hush_warnings()

    # ダブルクリックでも、このファイルの隣を探しにいけるようにする
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    try:
        from koyomi.ui.app import run
    except ImportError as trouble:
        # 拡張子の関連付けが別の Python に取られていると、ここへ来る。
        # 何が足りないかだけでは直しようがないので、どれで開いたかも伝える。
        sys.stderr.write(traceback.format_exc())
        announce(missing_parts(trouble))
        return 1
    return run()


if __name__ == "__main__":
    sys.exit(main())
