# 途强在线 Home Assistant 集成

这是一个面向 `https://www.tuqiangol.com` 的 Home Assistant 自定义集成。

功能包括：

- GPS 设备追踪器：经纬度和途强网站自己的地址
- 电池电量、速度、外接电压、总里程、GPS 信号、方向
- ACC、外接电源、设备状态、定位类型、定位时间、通讯时间
- “立即定位”按钮，对应网站的“下发指令 → 立即定位”
- 可选使用途强网站的“高精度定位地址”

安装
方式一：通过 HACS 自定义仓库（推荐）
确保已安装 HACS
在 HACS 中点击「集成」→ 右上角菜单 →「自定义存储库」
填写仓库地址：https://github.com/jimgo188/tuqiangol，类别选择「集成」
点击添加，然后在 HACS 中搜索「途强在线」并安装
重启 Home Assistant

方式二：手动安装
下载本仓库最新 Release 中的 tuqiangol.zip 并解压
将 custom_components/tuqiang_traccar 文件夹复制到您 Home Assistant 配置目录下的 custom_components 目录中
重启 Home Assistant
⚙️ 配置
第一步：添加集成
在 Home Assistant 中，前往「设置」→「设备与服务」→「添加集成」
搜索「途强在线」并点击
第二步：输入账号信息，并设置更新频率






