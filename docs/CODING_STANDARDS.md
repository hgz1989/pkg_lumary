# Python项目编码规范

## 1. 注释规范
- 类、函数注释采用三双引号格式，使用Google风格
- 参数、返回值仅写描述，不写类型，无返回值省略Returns
- 所有注释结尾不使用句号
- 所有模块必须添加头注释，包含作者、日期、模块描述，已有头注释仅可修改描述

## 2. 字符串规范
- 普通字符串使用单引号，字符串包含单引号需转义
- 格式化字符串统一使用f-string，f-string内部嵌套字符串使用双引号
- 中英文之间不需要空格

## 3. Python语法版本适配
- Python小于3.10：多类型注解使用Union，空类型使用Optional
- Python大于等于3.10：多类型注解使用“|”分隔符，空类型直接搭配None

## 4. 导入规范
- 优先使用from导入，易重名内容使用import导入
- 导入分为三类：标准库、第三方库、项目内部包，组间空行分隔
- 同组内import导入统一排在from导入前面，两类语句均按首字母 ASCII 排序
- `from` 语句中，`import` 后的对象必须**严格按照在代码中被首次调用的顺序排列**
- 当 `import` 后的对象列表超过 50 个字符时，使用 `()` 包裹，括号内每个导入对象单独一行，且**最后一个对象末尾严禁添加逗号**

## 5. Web接口规范
- 接口仅使用GET、POST、DELETE请求方法
- GET接口在前，分页查询接口放在所有GET接口末尾
- POST接口统一在后，DELETE接口在最后
- 仅物理删除时使用DELETE接口，逻辑删除时使用POST接口

## 6. SQLAlchemy ORM规范
- mapped_column严格按照原生参数顺序编写，参数单独换行
- 最后一个参数不添加尾逗号
- 主键字段末尾固定添加 sort_order=-10000

## 7. ORM职责规范
- ORM模型仅保留字段、索引、约束等数据结构相关内容
- 是否可用、是否过期等业务判断逻辑统一放在Service层

## 8. Pydantic Schema字段规范
- 所有字段必须显式使用Field定义
- Field参数严格遵循原生函数顺序
- 必填字段不使用...，所有字段必须填写描述
- Schema字段约束与ORM模型保持一致
- 数据库唯一性校验等需查库的逻辑，统一在业务层处理

## 9. Schema命名规范
- 模型类名不加Schema后缀
- 输入模型使用：Base、Create、Update
- 输出模型使用：Out、DetailOut，列表响应统一使用APIResponse[List[XXXOut]]
- 接口参数模型根据来源使用：Params、HeaderParams、PathParams

## 10. CRUD层规范
- CRUD类统一以CRUD为前缀，继承CRUDBase
- 简单业务场景仅需配置model属性

## 11. Service层基础规范
- Service构造函数统一接收 db: AsyncSession

## 12. Service层返回规范
- Service方法统一返回Out模型，通过model_validate转换ORM对象
- 数据库commit事务统一由Service层处理，CRUD层不提交事务

## 13. API注入规范
- 接口使用Annotated + Depends完成依赖注入

## 14. API参数规范
- 路径参数使用 Path(alias='xxx')
- 查询参数使用 Query

## 15. API缓存规范
- 所有接口缓存必须使用CacheManager
- 缓存键值对格式：{接口路径}_{请求参数}
- 缓存过期时间默认10秒
- 缓存值为JSON字符串，使用json.dumps编码

## 16. 所有__init__导出仅限于在自己的包内导出，不主动导出其他包的模块