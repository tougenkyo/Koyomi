"""English wording for the interface.

Keys are the Japanese source strings passed to ``i18n.tr()``.
Format specifiers (%s, %d, strftime codes) must survive unchanged, and the
order of positional specifiers must match the Japanese original.
Anything missing here simply falls back to Japanese.
"""

WORDS = {
    # ---- 断片・接尾辞 ------------------------------------------------------
    " の控え": " (copy)",
    " をまとめて": " (all)",
    " 分": " min",
    " 分（0 で拾わない）": " min (0 = do not look back)",
    " 分（0 で自動停止しない）": " min (0 = never stop by itself)",
    " 問": " questions",
    " 回（0 で無制限）": " times (0 = unlimited)",
    " 日": " days",
    " 日 休む": " days off",
    " 日 鳴らす": " days on",
    " 日ごと": " days apart",
    " 時間": " h",
    " 秒": " sec",
    " ＋登録日": " + saved dates",
    " ／ 期限切れ %d 件": " / %d overdue",
    "あと ": "in ",
    "に別の音を使う": " uses a different sound",
    "を除く": " excluded",
    "毎週 ": "Weekly ",
    "祝日を": "Holidays from",
    "試し鳴動 ｜ ": "Test ring | ",
    "設定の保存先:": "Settings are stored in:",

    # ---- 時間の言い回し ----------------------------------------------------
    "%Y年%m月%d日": "%b %d, %Y",
    "%d分": "%dm",
    "%d時間": "%dh",
    "%d日": "%dd",
    "%d秒": "%ds",
    "%d日 %d:%02d:%02d": "%dd %d:%02d:%02d",
    "%d日 超過": "%d days overdue",
    "まもなく": "any moment",
    "経過": "past",
    "今日": "today",
    "翌日": "next day",
    "前日": "previous day",
    "今日まで": "due today",
    "明日まで": "due tomorrow",
    "あと %d日": "%d days left",
    "現地と同じ": "same as local",
    "%s%d時間": "%s%dh",
    "%s%d時間%d分": "%s%dh%dm",
    "いまから %s": "%s from now",
    "全体 %s": "total %s",
    "%s に終了": "ends at %s",
    "終了しました": "finished",

    # ---- 曜日 --------------------------------------------------------------
    "月": "Mon",
    "火": "Tue",
    "水": "Wed",
    "木": "Thu",
    "金": "Fri",
    "土": "Sat",
    "日": "Sun",
    "%s曜日": "%s",
    "曜日": "Weekday",
    "毎日": "Every day",
    "平日": "Weekdays",
    "週末": "Weekends",
    "曜日未選択": "no weekday chosen",
    "週": "Week",
    "第%d": "week %d",
    "最終": "Last",
    "年": "",
    "月": "Mon",

    # ---- 繰り返し ----------------------------------------------------------
    "繰り返し": "Repeat",
    "繰り返さない": "No repeat",
    "日付を指定": "On a date",
    "曜日を指定": "By weekday",
    "N日おき": "Every N days",
    "毎月・日付": "Monthly by date",
    "毎月・第n曜日": "Monthly by weekday",
    "毎年": "Yearly",
    "鳴動／休止の周期": "On/off cycle",
    "1回だけ": "Once",
    "%d/%d に1回": "once on %d/%d",
    "%d日おき": "every %d days",
    "毎月 %d日": "day %d of every month",
    "毎月 末日": "last day of every month",
    "毎月 %s%s曜": "%s %s of every month",
    "毎年 %d/%d": "every year on %d/%d",
    "%d日鳴らして%d日休む": "%d days on, %d days off",
    "毎月": "Every month",
    "末日": "Last day",
    "周期": "Cycle",
    "起点の日": "Starting from",
    "鳴らす日": "Ring on",
    "次に来るこの時刻に 1 回だけ鳴らします。":
        "Rings once, at the next occurrence of this time.",
    "下のリストに入っている日も鳴らす": "Also ring on days in the lists below",

    # ---- 鳴らさない日 ------------------------------------------------------
    "鳴らさない日": "Days to skip",
    "祝日": "Holidays",
    "祝日を除く": "holidays excluded",
    "登録日を除く": "saved dates excluded",
    "日本の祝日は鳴らさない": "Never ring on Japanese public holidays",
    "日本の祝日は鳴らさない（jpholiday 未導入）":
        "Never ring on Japanese public holidays (jpholiday not installed)",
    "祝日は鳴らさない": "Skip holidays",
    "祝日でも鳴らす": "Ring on holidays too",
    "次の 1 回だけ飛ばす": "Skip just the next one",
    "次の1回だけ飛ばす": "Skip the next one",
    "次の1回を飛ばすのをやめる": "Stop skipping the next one",
    "次は飛ばす": "skipping next",
    "繰り返しのないアラームは飛ばせません。":
        "An alarm that does not repeat cannot be skipped.",

    # ---- 日付リスト --------------------------------------------------------
    "日付リストの管理": "Saved date lists",
    "日付リストの管理…": "Saved date lists…",
    "リスト": "List",
    "リスト名": "List name",
    "名前を変える": "Rename",
    "新しい名前": "New name",
    "登録されている日": "Saved dates",
    "日付をクリックすると登録／解除が切り替わります。":
        "Click a date to add or remove it.",
    "まとめて登録": "Add in bulk",
    "この期間の日本の祝日を取り込む": "Import Japanese holidays for this range",
    "祝日の取り込みには jpholiday が必要です":
        "Importing holidays needs the jpholiday package",
    "1年分を追加": "Add one year",
    "このリストを空にする": "Empty this list",
    "%d 件の祝日を追加しました。": "Added %d holidays.",
    "%d 件を追加しました。": "Added %d dates.",
    "「%s」の登録日をすべて消します。よろしいですか？":
        "This clears every date saved in \"%s\". Continue?",
    "取り込み": "Import",
    "%s（%d日）": "%s (%d days)",

    # ---- アラーム一覧 ------------------------------------------------------
    "アラーム": "Alarm",
    "アラームの設定": "Alarm settings",
    "アラームを追加": "Add an alarm",
    "アラームを追加しました。": "Alarm added.",
    "アラームがありません。": "There are no alarms.",
    "アラームが選ばれていません。": "No alarm is selected.",
    "アラーム名やグループ名で絞り込む": "Filter by alarm or group name",
    "アラーム名を左寄せにする": "Left-align alarm names",
    "まだアラームがありません。「＋ 追加」から作ってください。":
        "No alarms yet. Use \"+ Add\" to create one.",
    "条件に合うアラームがありません。": "No alarm matches the filter.",
    "次のアラーム": "Next alarm",
    "予定なし": "nothing scheduled",
    "%s ｜ 予定なし": "%s | nothing scheduled",
    "%s ｜ 次は %s（%s）": "%s | next %s (%s)",
    "%s に再通知": "again at %s",
    "%s に再通知します。": "Will ring again at %s.",
    "編集": "Edit",
    "複製": "Duplicate",
    "複製しました。": "Duplicated.",
    "削除": "Delete",
    "「%s」を削除します。よろしいですか？": "Delete \"%s\"?",
    "いま鳴らしてみる": "Try ringing it now",
    "検索": "Search",
    "メニュー": "Menu",
    "一覧": "List",
    "並び順": "Order",
    "並び順と表示": "Order and display",
    "設定時刻の早い順": "By time of day",
    "名前順": "By name",
    "グループ順": "By group",
    "ONを先に、次いで設定時刻": "On first, then time of day",
    "次に鳴る順": "By next ring",

    # ---- グループ ----------------------------------------------------------
    "グループ": "Group",
    "グループ名": "Group name",
    "グループ: すべて": "Group: all",
    "グループ: %s": "Group: %s",
    "グループ: %d件": "Group: %d",
    "すべて表示": "Show all",
    "グループの絞り込みを次回起動時も保つ": "Keep the group filter next time",
    "グループはアラームの絞り込みや、まとめて ON/OFF するときに使います。":
        "Groups are used for filtering and for switching alarms on or off together.",

    # ---- 一括操作 ----------------------------------------------------------
    "すべて ON": "All on",
    "すべて OFF": "All off",
    "すべてON": "All on",
    "すべてOFF": "All off",
    "ON にする": "Switch on",
    "OFF にする": "Switch off",
    "固定していないものだけ OFF": "Switch off everything not locked",
    "OFF のアラームを削除": "Delete alarms that are off",
    "OFFを削除": "Delete off",
    "OFF のアラームはありません。": "No alarms are switched off.",
    "OFF になっている %d件を削除します。よろしいですか？":
        "Delete the %d alarms that are switched off?",
    "%d件を%sにしました。": "Switched %d alarms %s.",
    "%s の %d件を%sにしました。": "In %s, switched %d alarms %s.",
    "%d件を止めました。": "Stopped %d alarms.",
    "%d件に反映しました。": "Applied to %d alarms.",
    "この時刻までを止める": "Silence until a time",
    "この時刻までを止める…": "Silence until a time…",
    "まとめて設定": "Change several at once",
    "まとめて設定…": "Change several at once…",
    "設定を変えるアラームを選んでください。": "Choose the alarms to change.",
    "変更する項目": "What to change",
    "チェックを入れた項目だけが上書きされます。":
        "Only the ticked rows are written to the chosen alarms.",
    "適用": "Apply",
    "実行": "Run",

    # ---- 鳴動画面 ----------------------------------------------------------
    "鳴動画面": "Ringing screen",
    "停止": "Stop",
    "停止・スヌーズ": "Stop and snooze",
    "止め方": "How to stop",
    "止め方　： %s": "Stop     : %s",
    "止める": "Stop",
    "止めたとき": "when stopped",
    "止めたらこのアラームを削除する": "Delete this alarm once it is stopped",
    "鳴り始めたとき": "when it starts ringing",
    "鳴動時": "on ring",
    "停止時": "on stop",
    "スヌーズ": "Snooze",
    "スヌーズ %d回目": "Snooze %d",
    "残り %d回": "%d left",
    "スヌーズ上限に達しました": "snooze limit reached",
    "スヌーズの上限に達したので停止しました。":
        "The snooze limit was reached, so the alarm stopped.",
    "スヌーズにします。よろしいですか？": "Snooze this alarm?",
    "このアラームを停止します。よろしいですか？": "Stop this alarm?",
    "確認": "Confirm",
    "%d秒だけ消音": "Mute for %d sec",
    "消音中…": "Muted…",
    "自動停止まで %d:%02d": "stops by itself in %d:%02d",
    "スヌーズを解除": "Cancel snooze",
    "スヌーズを解除しました。": "Snooze cancelled.",
    "スヌーズ間隔を変える": "Change the snooze interval",
    "何分後にしますか": "How many minutes from now?",
    "鳴らせなかったアラーム": "Alarms that did not ring",
    "アプリが動いていない間に、次のアラームの時刻が過ぎていました。":
        "These alarms were due while the app was not running.",
    "ほか %d件": "%d more",

    # ---- 解除方法 ----------------------------------------------------------
    "ボタンを押す": "Press a button",
    "長押しする": "Press and hold",
    "スライドする": "Slide",
    "計算問題を解く": "Solve arithmetic",
    "記号を順番にタップ": "Tap symbols in order",
    "色と形を選ぶ": "Pick a colour and shape",
    "スライドして%s": "Slide to %s",
    "%s（%.1f秒 長押し）": "%s (hold %.1f sec)",
    "%s（%.1f秒）": "%s (%.1f sec)",
    "%s／%s／%d問": "%s / %s / %d questions",
    "%s：%d問中 %d問 正解": "%s: %d questions, %d correct",
    "%s：この順に押してください（%d問中 %d問）":
        "%s: press them in this order (%d rounds, %d done)",
    "%s の %s を選んでください": "Pick the %s %s",
    "こたえる": "Answer",
    "数字を入力してください": "Type a number",
    "ちがいます。正解は %d でした。": "Wrong. The answer was %d.",
    "ちがいます。もう一度。": "Wrong. Try again.",
    "順番が違います。最初からやり直しです。": "Wrong order. Starting over.",
    "やさしい": "Easy",
    "ふつう": "Normal",
    "むずかしい": "Hard",
    "難しさ": "Difficulty",
    "出題数": "Questions",
    "操作方法": "Method",
    "長押しの時間": "Hold time",
    "確定前に確認する": "Ask before confirming",
    "この操作を試す": "Try this method",
    "操作の確認": "Method preview",
    "実際の鳴動画面と同じ操作です。試しても設定は変わりません。":
        "This is exactly what the ringing screen does. Trying it changes nothing.",
    "もどる": "Back",
    "まる": "circle",
    "しかく": "square",
    "さんかく": "triangle",
    "ひしがた": "diamond",
    "あか": "red",
    "あお": "blue",
    "きいろ": "yellow",
    "みどり": "green",
    "むらさき": "purple",

    # ---- スヌーズ設定 ------------------------------------------------------
    "スヌーズを使う": "Use snooze",
    "スヌーズを使わない": "Do not use snooze",
    "スヌーズのしかた": "How to snooze",
    "スヌーズ間隔": "Snooze interval",
    "スヌーズ： %s": "Snooze  : %s",
    "間隔": "Interval",
    "間隔の起点": "Counted from",
    "最大回数": "Maximum rounds",
    "無制限": "unlimited",
    "%d回": "%d times",
    "%d分 / 最大%s": "%d min / at most %s",
    "スヌーズ操作をした時刻から数える": "the moment you press snooze",
    "鳴り始めた時刻から数える": "the moment it started ringing",
    "鳴動画面で間隔を変えられるようにする":
        "Allow changing the interval on the ringing screen",
    "鳴動画面にスヌーズ回数を出す": "Show the snooze count while ringing",
    "スヌーズの回ごとに音を変える": "Use a different sound per snooze round",
    "1回目のスヌーズ": "1st snooze",
    "2回目のスヌーズ": "2nd snooze",
    "3回目以降": "3rd snooze onward",
    "鳴り続ける時間": "Keep ringing for",
    "鳴っている間": "While ringing",

    # ---- 音 ----------------------------------------------------------------
    "音": "Sound",
    "音　　　： %s / 音量 %d%%": "Sound    : %s / volume %d%%",
    "鳴らす音": "Alarm sound",
    "内蔵の音": "Built-in sound",
    "音声ファイル": "Audio file",
    "音声ファイル (%s)": "Audio files (%s)",
    "音声ファイルを選ぶ": "Choose an audio file",
    "フォルダからランダム": "Random from a folder",
    "フォルダを選ぶ": "Choose a folder",
    "音を鳴らさない": "No sound",
    "音量": "Volume",
    "だんだん大きく": "Fade in",
    "試聴": "Preview",
    "パスを選んでください": "Choose a path",
    "参照": "Browse",
    "鳴動画面だけを表示します。": "Only the ringing screen is shown.",
    "止めるまで繰り返す": "Repeat until stopped",
    "鳴り始めを 2 秒遅らせる": "Delay the start by 2 seconds",
    "きざし（やわらかい）": "Kizashi (gentle)",
    "しずく（水滴）": "Shizuku (droplets)",
    "かね（鐘）": "Kane (bell)",
    "ひびき（二音）": "Hibiki (two tones)",
    "あさいち（強め）": "Asaichi (insistent)",
    "せいれん（サイレン）": "Seiren (siren)",
    "指定した音声ファイルが見つからないため、内蔵音で鳴らしています。":
        "The chosen audio file was not found, so a built-in sound is playing.",
    "フォルダに再生できる音声が無いため、内蔵音で鳴らしています。":
        "The folder holds no playable audio, so a built-in sound is playing.",
    "この音声ファイルは再生できませんでした。内蔵音に切り替えます。":
        "That audio file could not be played. Falling back to a built-in sound.",
    "音声を再生できる仕組みが見つかりませんでした。":
        "No way to play audio was found on this machine.",

    # ---- 基本・画面 --------------------------------------------------------
    "基本": "Basics",
    "画面": "Display",
    "時刻": "Time",
    "時刻　　： %s": "Time     : %s",
    "時刻と名前": "Time and name",
    "鳴らす時刻": "Ring at",
    "名前": "Name",
    "名前（省略可）": "Name (optional)",
    "空欄なら「アラーム」になります": "Left blank, it becomes \"Alarm\"",
    "（無題）": "(untitled)",
    "画面のふちを点滅させる": "Flash the window border",
    "文字を小さめにする": "Use smaller text",
    "誤操作の防止": "Guard against slips",
    "一覧の ON/OFF スイッチを固定する": "Lock the on/off switch in the list",
    "固定": "locked",
    "スイッチを固定する": "Lock the switch",
    "スイッチの固定を解く": "Unlock the switch",
    "固定を解く": "Unlock",
    "ON/OFF の固定": "Switch lock",
    "繰り返し： %s": "Repeat   : %s",

    # ---- 連動動作 ----------------------------------------------------------
    "連動": "Companion",
    "連動動作の確認": "Companion actions",
    "このアラームで連動動作を使う": "Run a companion action with this alarm",
    "何をするか": "What to do",
    "引数": "Arguments",
    "ページ": "Page",
    "いつ": "When",
    "起動するファイルを選ぶ": "Choose a file to start",
    "https://…（省略可）": "https://… (optional)",
    "指定されたファイルが見つかりません: %s": "That file does not exist: %s",
    "URL は http:// または https:// で始めてください。":
        "The URL must start with http:// or https://.",
    "引数の引用符が閉じていません。": "There is an unclosed quote in the arguments.",
    "%s を起動しました。": "Started %s.",
    "起動できませんでした: %s": "Could not start it: %s",
    "起動できませんでした（ファイルが見つかりません）。":
        "Could not start it (the file is missing).",
    "ページを開きました。": "Opened the page.",
    "ページを開けませんでした: %s": "Could not open the page: %s",
    "この URL は開けません（http/https のみ）。":
        "That URL cannot be opened (http/https only).",
    "このアラームの連動動作は未承認のため実行しませんでした。":
        "This alarm's companion action is not approved yet, so it was skipped.",
    "読み込んだアラームに、アプリやページを開く指定が含まれています。":
        "Some of the alarms you loaded start programs or open pages.",
    "身に覚えのないものは「使わない」を選んでください。":
        "If you do not recognise them, choose No.",

    "%s を開きました。": "Opened %s.",
    "開くもの": "What to open",
    "アプリ・画像・文書など（省略可）": "App, image, document… (optional)",
    "引数（省略可・実行ファイルのときだけ使われます）":
        "Arguments (optional, used only for executables)",
    "アラームに合わせて、アプリやファイルを開いたり、Web ページを表示したりします。":
        "Open an app or a file, or show a web page, along with the alarm.",

    # ---- 設定 --------------------------------------------------------------
    "設定": "Settings",
    "設定…": "Settings…",
    "保存": "Save",
    "やめる": "Cancel",
    "閉じる": "Close",
    "開く": "Open",
    "戻す": "Reset",
    "リセット": "Reset",
    "解除": "Clear",
    "追加": "Add",
    "新規作成の初期値": "Defaults for new alarms",
    "初期値を編集する": "Edit the defaults",
    "初期値を工場出荷時に戻す": "Restore the original defaults",
    "下部のクイックメニュー": "Bottom quick menu",
    "クイックメニューを表示する": "Show the quick menu",
    "6 つの中から 3 つを選びます。": "Pick 3 of the 6 actions.",
    "お知らせ": "Notifications",
    "タスクトレイに次のアラーム時刻を出す": "Show the next alarm in the tray tooltip",
    "自動停止したときに知らせる": "Tell me when an alarm stops by itself",
    "重なったとき": "When alarms overlap",
    "鳴動中なら後から来た方をスヌーズにする": "Snooze the later alarm",
    "鳴動中なら後から来た方を止める": "Drop the later alarm",
    "鳴動中でも別ウィンドウで重ねて鳴らす": "Ring both in separate windows",
    "起動時に取りこぼしを拾う範囲": "Look back for missed alarms",
    "常駐しています。アラームは動き続けます。":
        "Still running in the tray. Alarms keep working.",
    "ウィンドウを開く": "Open the window",
    "終了": "Quit",
    "このアプリについて": "About",
    "デスクトップ向けの目覚ましアプリです。": "An alarm clock for the desktop.",

    # ---- 外観 --------------------------------------------------------------
    "外観": "Appearance",
    "配色": "Colours",
    "ことば": "Language",
    "切り替えたあと、アプリを開き直すとすべての画面に行き渡ります。":
        "Reopen the app after switching so every screen picks it up.",
    "フローティング表示": "Floating panel",
    "フローティング表示を出す": "Show the floating panel",
    "フローティング表示をしまう": "Hide the floating panel",
    "小さな窓を画面のすみに出しておく": "Keep a small panel in a corner of the screen",
    "夜市": "Night market",
    "炭火": "Charcoal",
    "白亜": "Chalk",
    "琥珀": "Amber",
    "空": "Sky",
    "若草": "Fresh green",
    "藤": "Wisteria",
    "珊瑚": "Coral",
    "紅": "Crimson",
    "露草": "Dayflower",
    "山吹": "Marigold",
    "青竹": "Bamboo",
    "最前面": "On top",

    # ---- 電源 --------------------------------------------------------------
    "電源": "Power",
    "時刻に合わせて PC を起こす": "Wake the PC for an alarm",
    "スリープ中でも、次のアラームの少し前に復帰させる":
        "Resume from sleep shortly before the next alarm",
    "アラームが鳴っている間はスリープさせない":
        "Do not let the PC sleep while an alarm is ringing",
    "決めた時刻に PC をスリープさせる": "Put the PC to sleep at a set time",
    "使う": "Use this",
    "使わない": "Do not use",
    "設定時刻になったので PC をスリープさせます。":
        "The set time has arrived, so the PC will sleep.",
    "いまの予約状況を確かめる": "Check the current state",
    "ここに確認結果が出ます。": "The result appears here.",
    "スリープ解除タイマーの許可": "Allow wake timers",
    "  電源に接続中 : %s": "  On mains  : %s",
    "  バッテリー駆動: %s": "  On battery: %s",
    "利用可能": "available",
    "未導入": "not installed",
    "不明": "unknown",
    "予約されているスリープ解除タイマーはありません。": "No wake timers are set.",
    "（予約の一覧は管理者権限が無いと表示できません）":
        "(listing the timers needs administrator rights)",
    "電源設定を読み取れませんでした。": "The power settings could not be read.",
    "コントロールパネル → 電源オプション → プラン設定の変更 →":
        "Control Panel > Power Options > Change plan settings >",
    "詳細な電源設定の変更 → スリープ → スリープ解除タイマーの許可":
        "Change advanced power settings > Sleep > Allow wake timers",
    "を「有効」にしてください。": "Set it to Enable.",
    "この OS では確認できません。": "This cannot be checked on this OS.",
    "この OS では電源まわりの操作に対応していません。":
        "Power control is not supported on this OS.",
    "タイマーを作成できませんでした。": "The timer could not be created.",
    "タイマーを設定できませんでした。": "The timer could not be set.",

    # ---- データ ------------------------------------------------------------
    "データ": "Data",
    "保存場所": "Where things are kept",
    "フォルダを開く": "Open the folder",
    "バックアップ": "Backup",
    "バックアップを作る": "Create a backup",
    "バックアップから戻す": "Restore from a backup",
    "バックアップの保存先": "Where to save the backup",
    "バックアップを選ぶ": "Choose a backup",
    "バックアップから戻しました。": "Restored from the backup.",
    "戻すと、いまのアラームと設定はすべて置き換わります。":
        "Restoring replaces every alarm and setting you have now.",
    "いまのアラームと設定をすべて置き換えます。よろしいですか？":
        "This replaces every alarm and setting. Continue?",
    "書き出しました。\n%s": "Saved.\n%s",
    "保存できません": "Cannot save",
    "読み込めません": "Cannot read",
    "このファイルはバックアップとして読み込めません。":
        "This file cannot be read as a backup.",
    "復元": "Restore",
    "設定を保存できませんでした: %s": "The settings could not be saved: %s",

    # ---- タイマー ----------------------------------------------------------
    "タイマー": "Timer",
    "タイマー・ストップウォッチ…": "Timers and stopwatches…",
    "カウントダウン": "Countdown",
    "すぐ足す": "Quick add",
    "よく使う時間を編集": "Edit the quick durations",
    "よく使う時間 %d": "Quick duration %d",
    "秒数": "Seconds",
    "新しいタイマー": "New timer",
    "日時を指定して計る": "Count to a date and time",
    "長さで指定する": "Count a duration",
    "未来の時刻を指定してください。": "Choose a time in the future.",
    "開始": "Start",
    "一時停止": "Pause",
    "登録中 %d／%d 本": "%d of %d timers",
    "「%s」の時間になりました。": "\"%s\" is up.",
    "タイマー %d本 ／ 最短 %s": "%d timers / soonest %s",
    "タイマーを閉じる": "Closing timers",

    # ---- ストップウォッチ --------------------------------------------------
    "ストップウォッチ": "Stopwatch",
    "ストップウォッチ %d": "Stopwatch %d",
    "＋ 新しいストップウォッチ": "+ New stopwatch",
    "開いている台数: %d": "Open: %d",
    "開いている窓をすべて前面に出す": "Bring every open window to the front",
    "ストップウォッチは 1 台ずつ別の窓で開きます。\n何台でも並べられ、それぞれ独立して計れます。":
        "Each stopwatch opens in its own window.\n"
        "You can keep as many as you like, each timing independently.",
    "スタート": "Start",
    "再開": "Resume",
    "ラップ": "Lap",
    "ラップ %d   %s   （通算 %s）": "Lap %d   %s   (total %s)",
    "秒の表示": "Seconds shown as",
    "1秒": "1 s",
    "0.1秒": "0.1 s",
    "0.01秒": "0.01 s",
    "0.001秒": "0.001 s",
    "0秒": "0 s",

    # ---- 世界時計 ----------------------------------------------------------
    "世界時計": "World clock",
    "世界時計…": "World clock…",
    "上の欄から都市を選んで追加してください。": "Pick a city above and add it.",
    "ほかの地域を探す（例: Lisbon, Cairo, Asia/）":
        "Search other zones (e.g. Lisbon, Cairo, Asia/)",
    "この地域は表示できません": "This zone cannot be shown",
    "地域データ（tzdata）が見つからないため、時刻を出せません。":
        "Time zone data (tzdata) is missing, so no times can be shown.",
    "東京": "Tokyo",
    "ソウル": "Seoul",
    "北京・上海": "Beijing / Shanghai",
    "台北": "Taipei",
    "香港": "Hong Kong",
    "シンガポール": "Singapore",
    "バンコク": "Bangkok",
    "デリー": "Delhi",
    "ドバイ": "Dubai",
    "モスクワ": "Moscow",
    "ベルリン": "Berlin",
    "パリ": "Paris",
    "ロンドン": "London",
    "ニューヨーク": "New York",
    "シカゴ": "Chicago",
    "デンバー": "Denver",
    "ロサンゼルス": "Los Angeles",
    "ホノルル": "Honolulu",
    "メキシコシティ": "Mexico City",
    "サンパウロ": "Sao Paulo",
    "シドニー": "Sydney",
    "オークランド": "Auckland",
    "協定世界時 (UTC)": "Coordinated Universal Time (UTC)",

    # ---- やることリスト ----------------------------------------------------
    "やることリスト": "To-do list",
    "やることリスト…": "To-do list…",
    "やること": "To do",
    "やることを書いて Enter": "Type something to do, then press Enter",
    "詳しく書く": "Add with details",
    "メモ": "Note",
    "例: 電池を買う": "e.g. buy batteries",
    "優先度": "Priority",
    "高": "High",
    "中": "Mid",
    "低": "Low",
    "期限": "Due",
    "済んだものを隠す": "Hide finished items",
    "済んだものを削除": "Delete finished items",
    "まだ何もありません。上の欄から追加してください。":
        "Nothing here yet. Add something using the box above.",
    "全 %d 件 ／ 済 %d 件": "%d items / %d done",

    "アラームの予定なし": "no alarm scheduled",
    "＋ 追加": "+ Add",
    "「%s」は別のアラームと重なったのでスヌーズにしました。":
        "\"%s\" clashed with another alarm, so it was snoozed.",
    "「%s」は別のアラームと重なったため見送りました。":
        "\"%s\" clashed with another alarm, so it was skipped.",
    "「%s」は時間が来たので自動停止しました。":
        "\"%s\" ran out of time and stopped by itself.",
    "「%s」は自動停止し、%s に再通知します。":
        "\"%s\" stopped by itself and will ring again at %s.",

    # ---- 長めの説明文 ------------------------------------------------------
    "Windows の電源オプションで「スリープ解除タイマーの許可」が有効になっている必要があります。休止状態や電源を切った状態からは復帰できません。":
        "Windows must have \"Allow wake timers\" enabled in Power Options. "
        "The PC cannot resume from hibernation or from being switched off.",
    "「無効」になっている状態では、スリープ中に PC を起こせません。":
        "While this is disabled, the PC cannot be woken for an alarm.",
    "「追加」で新しいアラームを作るときの初期値です。すでにあるアラームには影響しません。":
        "These are the starting values for alarms made with Add. "
        "Alarms you already have are untouched.",
    "このアラームはスイッチが固定されています。右クリックから解除できます。":
        "This alarm's switch is locked. Unlock it from the right-click menu.",
    "この設定はアプリを起動します。バックアップから読み込んだアラームの連動動作は、内容を確認して承認するまで動きません。":
        "This setting starts a program. Companion actions loaded from a backup "
        "stay inert until you review and approve them.",
    "ストップウォッチは 1 台ずつ別の窓で開きます。\n何台でも並べられ、それぞれ独立して計れます。":
        "Each stopwatch opens in its own window.\n"
        "You can keep as many as you like, each timing independently.",
    "下地 3 系統とさし色 9 色の組み合わせで %d 通りあります。選ぶとその場で反映されます。":
        "Three backdrops and nine accent colours make %d combinations. "
        "Picking one applies it straight away.",
    "今日のこの時刻までに鳴る予定のアラームを止めます。\n繰り返しのあるものは「次の1回だけ飛ばす」になります。":
        "Silences every alarm due before this time today.\n"
        "Repeating alarms are set to skip just the next one.",
    "作業中でもそのままスリープに入ります。アラームが鳴っている間とスヌーズ中は見送ります。":
        "It sleeps even while you are working. "
        "It holds off while an alarm is ringing or snoozing.",
    "固定中は一覧から切り替えられません。解除はこの画面か、一覧の右クリックメニューから行えます。":
        "While locked, the switch cannot be flipped from the list. "
        "Unlock it here or from the right-click menu.",
    "次のアラームと、走っているタイマーの残りを常に表示します。どこを掴んでも動かせます。":
        "Always shows the next alarm and any running timers. "
        "Drag it from anywhere to move it.",
    "祝日の判定は公開ライブラリ jpholiday を利用しています（%s）。":
        "Public holidays come from the jpholiday package (%s).",

    # ---- 区切りと既定の名前 ------------------------------------------------
    "（%s）": " (%s)",
    "・": ", ",
    "、": ", ",
    "グループ 1": "Group 1",
    "グループ 2": "Group 2",
    "グループ 3": "Group 3",
    "グループ 4": "Group 4",
    "グループ 5": "Group 5",
    "日付リスト 1": "Date list 1",
    "日付リスト 2": "Date list 2",
    "日付リスト 3": "Date list 3",
    "日付リスト 4": "Date list 4",
    "日付リスト 5": "Date list 5",
    "日付リスト 6": "Date list 6",
    "日付リスト 7": "Date list 7",
    "日付リスト 8": "Date list 8",

    # ---- 自動起動と多重起動 ------------------------------------------------
    "Windows の起動時に始める": "Start with Windows",
    "Windows を起動したら、このアプリも開始する":
        "Start this app when Windows starts",
    "そのときはトレイに畳んでおく": "Start folded into the tray",
    "Windows の設定を開く": "Open Windows settings",
    "登録し直す": "Register again",
    "自動起動の登録": "Startup registration",
    "自動起動を登録し直しました。": "Startup was registered again.",
    "登録されていません。": "Not registered.",
    "登録済み。次回の Windows 起動から始まります。":
        "Registered. It will start with the next Windows boot.",
    "別の場所が登録されています。登録し直してください。":
        "Another location is registered. Please register again.",
    "登録はありますが、タスクマネージャーで無効にされています。":
        "It is registered, but Task Manager has it disabled.",
    "この OS では自動起動に対応していません。":
        "Starting with the system is not supported on this OS.",
    "登録できませんでした: %s": "Could not register: %s",
    "解除できませんでした: %s": "Could not unregister: %s",
    "このフォルダを移動すると登録が外れます。移動したときは「登録し直す」を押してください。":
        "Moving this folder breaks the registration. "
        "Press Register again after a move.",
    "Windows 起動時に開く設定が、いまと違う場所を指しています。この場所で登録し直しますか？":
        "The start-with-Windows entry points somewhere else. "
        "Register this location instead?",
    "すでに動いています。こちらの窓を使ってください。":
        "It is already running. Use this window.",
    "窓口を閉じる": "Closing the instance guard",

    # ---- 更新 --------------------------------------------------------------
    "更新": "Updates",
    "更新の確認": "Check for updates",
    "更新を確認…": "Check for updates…",
    "起動したときに新しい版が出ていないか調べる":
        "Look for a newer version at startup",
    "調べるときだけ GitHub へ問い合わせます。切っていても、メニューの「更新を確認」からいつでも調べられます。":
        "It reaches GitHub only while checking. Even when this is off, "
        "you can check any time from the menu.",
    "調べています…": "Checking…",
    "いまの版: %s": "Installed: %s",
    "いまの版: %s ／ 向こうの版: %s": "Installed: %s / Available: %s",
    "最新版を使っています。": "You are on the latest version.",
    "新しい版 %s があります。": "Version %s is available.",
    "新しい版 %s が出ています。": "Version %s is out.",
    "新しい版 %s が出ています。メニューの「更新を確認」から取り込めます。":
        "Version %s is out. Use Check for updates in the menu to get it.",
    "確認できませんでした。": "The check did not go through.",
    "通信できなかったようです。": "The connection did not work.",
    "調べられませんでした: %s": "Could not check: %s",
    "向こうの版番号を読み取れませんでした。":
        "The version number could not be read.",
    "配布ページを開く": "Open the project page",
    "いまの場所を更新する": "Update this copy",
    "取り込んでいます…": "Fetching…",
    "取り込みました。開き直すと新しい版になります。":
        "Fetched. Reopen the app to run the new version.",
    "取り込めませんでした。": "The update did not go through.",
    "開き直して反映する": "Reopen to apply",
    "開き直せませんでした。手で起動し直してください。":
        "Could not reopen. Please start it again yourself.",
    "この場所は git の作業コピーではないため、自動では取り込めません。":
        "This copy is not a git working tree, so it cannot update itself.",
    "取り込み元が設定されていません。": "No upstream is set.",
    "手元に未保存の変更があります。先にコミットするか元に戻してください。":
        "There are uncommitted changes here. Commit or discard them first.",

    # ---- 終了処理・その他 --------------------------------------------------
    "[%s] 終了処理でつまずきました: %s: %s": "[%s] Shutdown step failed: %s: %s",
    "時刻の記録": "Recording the time",
    "見張りの停止": "Stopping the watcher",
    "鳴動画面を閉じる": "Closing ringing screens",
    "小窓を閉じる": "Closing side windows",
    "設定の保存": "Saving settings",
    "音の停止": "Stopping sound",
    "トレイアイコンの削除": "Removing the tray icon",
}
