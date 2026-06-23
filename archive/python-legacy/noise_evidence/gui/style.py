"""淡雅浅色主题 —— "宣纸·黛青"。

设计取向（中国素雅、护眼、长时间复核不累）:
  - 背景: 宣纸暖白，低饱和、偏暖，替代刺眼的深色高对比。
  - 文字: 墨色（暖深灰），柔和不死黑。
  - 点缀: 黛青/竹青（青瓷绿），克制内敛，只在主操作与选中处出现。
  - 警示: 赭石暖橙，替代刺眼的纯红。
  - 圆角、细暖灰描边、充足留白，营造文人书案般的雅致。

色板（中国传统色意象）:
  宣纸 #F3EFE6 / 月白 #FBFAF6 / 墨 #34312B / 黛 #6E685B
  竹青(主) #4F7E6E / 青瓷(浅) #E4ECE6 / 赭石 #B07B52
"""

from __future__ import annotations

STYLE_SHEET = """
QWidget {
    background-color: #F3EFE6;
    color: #34312B;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}

/* 普通按钮：月白底、暖灰描边 */
QPushButton {
    background-color: #FBFAF6;
    border: 1px solid #D7CFBE;
    border-radius: 8px;
    padding: 7px 14px;
    color: #4A463D;
}
QPushButton:hover {
    background-color: #F0ECE2;
    border-color: #C2B9A4;
}
QPushButton:pressed {
    background-color: #E8E3D7;
}
QPushButton:disabled {
    color: #B3AC9B;
    background-color: #F1EDE4;
    border-color: #E0DACB;
}
QPushButton#toggle:checked {
    background-color: #E4ECE6;
    border-color: #4F7E6E;
    color: #345C50;
    font-weight: 600;
}
QPushButton#danger {
    color: #8C4D3F;
    border-color: #D4B5A9;
}
QPushButton#danger:hover {
    background-color: #F3E6E1;
    border-color: #B06A59;
}
QPushButton#smallDanger {
    padding: 4px 8px;
    color: #8C4D3F;
    border-color: #D4B5A9;
}
QPushButton#smallDanger:hover {
    background-color: #F3E6E1;
    border-color: #B06A59;
}

/* 主操作按钮：竹青强调 */
QPushButton#primary {
    background-color: #4F7E6E;
    border: 1px solid #4F7E6E;
    color: #FBFAF6;
    font-weight: 600;
}
QPushButton#primary:hover {
    background-color: #5C8E7D;
    border-color: #5C8E7D;
}
QPushButton#primary:pressed {
    background-color: #436B5D;
}
QPushButton#primary:disabled {
    background-color: #BFD0C8;
    border-color: #BFD0C8;
    color: #EDF2EF;
}

/* 文件名 / 提示文字 */
QLabel#hint {
    color: #938C7C;
}
QLabel#stats {
    background-color: #FBFAF6;
    border: 1px solid #E2DBCB;
    border-radius: 10px;
    padding: 14px;
    line-height: 150%;
}

/* 复选框 */
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1.5px solid #C2B9A4;
    background-color: #FBFAF6;
}
QCheckBox::indicator:hover {
    border-color: #4F7E6E;
    background-color: #F0ECE2;
}
QCheckBox::indicator:checked {
    background-color: #4F7E6E;
    border-color: #4F7E6E;
    image: url("__CHECK__");
}
QCheckBox::indicator:checked:hover {
    background-color: #5C8E7D;
    border-color: #5C8E7D;
}
QCheckBox::indicator:disabled {
    border-color: #E0DACB;
    background-color: #F1EDE4;
}

/* 下拉框 / 数值框 */
QComboBox, QDoubleSpinBox, QSpinBox {
    background-color: #FBFAF6;
    border: 1px solid #D7CFBE;
    border-radius: 8px;
    padding: 4px 24px 4px 10px;
    color: #4A463D;
    min-width: 90px;
    min-height: 24px;
}
QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover {
    border-color: #C2B9A4;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background-color: #FBFAF6;
    border: 1px solid #D7CFBE;
    selection-background-color: #4F7E6E;
    selection-color: #FBFAF6;
    color: #4A463D;
    outline: none;
}
QDoubleSpinBox::up-button, QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border: none;
    border-top-right-radius: 7px;
    background-color: #EFEADF;
}
QDoubleSpinBox::down-button, QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border: none;
    border-bottom-right-radius: 7px;
    background-color: #EFEADF;
}
QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {
    background-color: #E2DBCB;
}
QDoubleSpinBox::up-button:pressed, QSpinBox::up-button:pressed,
QDoubleSpinBox::down-button:pressed, QSpinBox::down-button:pressed {
    background-color: #D7CFBE;
}
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
    image: url("__ARROW_UP__");
    width: 9px;
    height: 9px;
}
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
    image: url("__ARROW_DOWN__");
    width: 9px;
    height: 9px;
}
QComboBox::down-arrow {
    image: url("__ARROW_DOWN__");
    width: 10px;
    height: 10px;
}

/* 分隔竖线 */
QFrame#sep {
    color: #DED7C7;
    max-width: 1px;
}

/* 进度条 */
QProgressBar {
    background-color: #EDE8DC;
    border: 1px solid #DED7C7;
    border-radius: 8px;
    height: 22px;
    text-align: center;
    color: #4A463D;
}
QProgressBar::chunk {
    background-color: #4F7E6E;
    border-radius: 7px;
}

/* 事件表 */
QTableWidget {
    background-color: #FBFAF6;
    border: 1px solid #E2DBCB;
    border-radius: 10px;
    gridline-color: #ECE6D9;
    selection-background-color: #E4ECE6;
    selection-color: #34312B;
    outline: none;
}
QTableWidget::item {
    padding: 4px 6px;
    border: none;
}
QHeaderView::section {
    background-color: #EFEADF;
    color: #6E685B;
    border: none;
    border-bottom: 1px solid #DED7C7;
    padding: 7px 6px;
    font-weight: 600;
}
QTableWidget QTableCornerButton::section {
    background-color: #EFEADF;
    border: none;
}

/* 滚动条 */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #D2C9B6;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #C2B9A4;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #D2C9B6;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ℹ️ 说明小圆钮：圆形、低调，悬停显示通俗解释 */
QPushButton#help {
    background-color: #E4ECE6;
    border: 1px solid #C4D4CB;
    border-radius: 9px;
    padding: 0;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    color: #4F7E6E;
    font-weight: 700;
    font-size: 12px;
}
QPushButton#help:hover {
    background-color: #4F7E6E;
    border-color: #4F7E6E;
    color: #FBFAF6;
}

/* 设置分区卡片：把相关选项收进一个带标题的浅色面板，降低认知负荷 */
QFrame#card {
    background-color: #FBFAF6;
    border: 1px solid #E2DBCB;
    border-radius: 8px;
}
QLabel#cardTitle {
    color: #6E685B;
    font-weight: 600;
}
QLabel#fieldLabel {
    color: #6E685B;
}
QLabel#empty {
    color: #938C7C;
    background-color: transparent;
}

/* 模式选择下拉：略微强调，作为流程的第一步 */
QComboBox#mode {
    min-width: 220px;
    font-weight: 600;
}

/* 消息框 */
QMessageBox {
    background-color: #FBFAF6;
}
QToolTip {
    background-color: #FBFAF6;
    color: #4A463D;
    border: 1px solid #D7CFBE;
    border-radius: 6px;
    padding: 6px 10px;
}
"""


def build_style_sheet() -> str:
    """返回可用的样式表：把图片占位符替换为真实绝对路径。

    Qt QSS 的 url() 需要正斜杠路径，这里统一转换，兼容开发与打包环境。
    """
    from ..resources import asset_path

    return (
        STYLE_SHEET.replace("__CHECK__", asset_path("check.png").as_posix())
        .replace("__ARROW_UP__", asset_path("arrow_up.png").as_posix())
        .replace("__ARROW_DOWN__", asset_path("arrow_down.png").as_posix())
    )
