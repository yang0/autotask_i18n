try:
    from autotask.nodes import Node, GeneratorNode, ConditionalNode, register_node
except ImportError:
    from stub import Node, GeneratorNode, ConditionalNode, register_node

from typing import Dict, Any, Generator, List
import os
import re
import json


@register_node
class GenerateTypesTS(Node):
    NAME = "获取types.ts"
    DESCRIPTION = "根据zh.ts文件生成types.ts文件"

    INPUTS = {
        "zh_ts_file": {
            "label": "zh.ts文件路径",
            "description": "中文翻译文件的路径",
            "type": "STRING",
            "required": True,
        },
        "output_dir": {
            "label": "输出目录",
            "description": "types.ts文件的输出目录",
            "type": "STRING",
            "required": True,
        },
    }

    OUTPUTS = {
        "result": {
            "label": "types.ts路径",
            "description": "生成的types.ts文件路径",
            "type": "STRING",
        }
    }

    async def execute(self, node_inputs: Dict[str, Any], workflow_logger) -> Dict[str, Any]:
        try:
            zh_ts_file = node_inputs["zh_ts_file"]
            output_dir = node_inputs["output_dir"]

            workflow_logger.info(f"Reading zh.ts file from: {zh_ts_file}")

            # 读取zh.ts文件内容
            with open(zh_ts_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 提取接口结构
            interface_content = self._generate_interface(content)

            # 生成完整的types.ts内容
            types_content = f"""export interface I18nMessages {interface_content}

"""
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)

            # 写入types.ts文件
            output_file = os.path.join(output_dir, "types.ts")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(types_content)

            workflow_logger.info(f"Successfully generated types.ts at: {output_file}")

            return {"success": True, "result": output_file}

        except Exception as e:
            workflow_logger.error(f"Failed to generate types.ts: {str(e)}")
            return {"success": False, "error_message": str(e)}

    def _generate_interface(self, content: str) -> str:
        """根据zh.ts内容生成TypeScript接口定义"""
        def parse_ts_object(content: str) -> List[str]:
            """直接解析TypeScript对象为接口定义行"""
            lines = []
            indent_level = 0
            
            for line in content.split('\n'):
                line = line.strip()
                if not line or line == 'export default {':
                    continue
                    
                # 处理对象结束
                if line in ['}', '},']:
                    indent_level -= 1
                    if indent_level >= 0:  # 避免最外层的结束括号
                        lines.append("  " * indent_level + "}")
                    continue
                    
                # 处理键值对
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().strip("'").strip('"')
                    value = value.strip().rstrip(',')
                    
                    indent_str = "  " * indent_level
                    
                    # 处理嵌套对象
                    if value.strip() == '{':
                        lines.append(f"{indent_str}{key}: {{")
                        indent_level += 1
                    # 处理字符串值
                    elif value.strip().startswith("'") or value.strip().startswith('"'):
                        lines.append(f"{indent_str}{key}: string")
                    
            return lines

        # 提取export default后的对象内容
        match = re.search(r'export\s+default\s+({[\s\S]+})', content)
        if not match:
            raise ValueError("Invalid zh.ts file format")
        
        obj_content = match.group(1)
        interface_lines = parse_ts_object(obj_content)
        
        return "{\n" + "\n".join(line for line in interface_lines if line.strip()) + "\n}"


@register_node
class CompareI18nKeys(Node):
    NAME = "比较国际化文件"
    DESCRIPTION = "比较两个国际化文件的key是否一致"

    INPUTS = {
        "first_file": {
            "label": "文件1路径",
            "description": "第一个国际化文件的路径",
            "type": "STRING",
            "required": True,
        },
        "second_file": {
            "label": "文件2路径",
            "description": "第二个国际化文件的路径",
            "type": "STRING",
            "required": True,
        }
    }

    OUTPUTS = {
        "is_identical": {
            "label": "是否一致",
            "description": "两个文件的key是否完全一致",
            "type": "BOOLEAN",
        },
        "missing_keys": {
            "label": "缺失的key",
            "description": "两个文件中互相缺失的key列表",
            "type": "DICT",
        }
    }

    def _extract_keys(self, content: str) -> set:
        """提取ts文件中所有的key"""
        import json
        keys = set()
        
        def collect_keys(obj: dict, prefix=""):
            """递归收集所有key"""
            for key, value in obj.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    collect_keys(value, full_key)
                else:
                    keys.add(full_key)
            return keys

        try:
            # 提取export default后的对象内容
            match = re.search(r'export\s+default\s+({[\s\S]+})\s*$', content)
            if not match:
                raise ValueError("Invalid i18n file format: missing 'export default'")
                
            # 将ts对象转换为合法的JSON格式
            obj_content = match.group(1)
            
            # 处理TypeScript对象格式
            # 1. 处理key (确保所有key都有引号)
            obj_content = re.sub(r'(?m)^(\s*)(\w+):', r'\1"\2":', obj_content)
            
            # 2. 处理字符串值 (将单引号转换为双引号)
            obj_content = re.sub(r"'([^']*)'", r'"\1"', obj_content)
            
            # 3. 移除尾随逗号
            obj_content = re.sub(r',(\s*[}\]])', r'\1', obj_content)
            
            try:
                i18n_dict = json.loads(obj_content)
                return collect_keys(i18n_dict)
            except json.JSONDecodeError as e:
                workflow_logger.error(f"JSON parsing error: {str(e)}")
                workflow_logger.error(f"Processed content: {obj_content}")
                raise ValueError(f"Failed to parse i18n content: {str(e)}")
                
        except Exception as e:
            workflow_logger.error(f"Error extracting keys: {str(e)}")
            raise ValueError(f"Failed to process i18n file: {str(e)}")

    async def execute(self, node_inputs: Dict[str, Any], workflow_logger) -> Dict[str, Any]:
        try:
            file1 = node_inputs["first_file"]
            file2 = node_inputs["second_file"]

            workflow_logger.info(f"Comparing i18n files: {file1} and {file2}")

            # 读取两个文件内容
            with open(file1, "r", encoding="utf-8") as f:
                content1 = f.read()
            with open(file2, "r", encoding="utf-8") as f:
                content2 = f.read()

            # 提取文件名
            file1_name = os.path.basename(file1)
            file2_name = os.path.basename(file2)

            # 提取两个文件的所有key
            keys1 = self._extract_keys(content1)
            keys2 = self._extract_keys(content2)

            # 比较key
            missing_in_2 = sorted(list(keys1 - keys2))
            missing_in_1 = sorted(list(keys2 - keys1))
            
            is_identical = len(missing_in_1) == 0 and len(missing_in_2) == 0
            
            result = {
                "is_identical": is_identical,
                "missing_keys": {
                    f"missing_in_{file2_name}": missing_in_2,
                    f"missing_in_{file1_name}": missing_in_1
                }
            }

            if not is_identical:
                workflow_logger.warning(f"Found mismatched keys between {file1_name} and {file2_name}")
                if missing_in_2:
                    workflow_logger.warning(f"Keys missing in {file2_name}: {missing_in_2}")
                if missing_in_1:
                    workflow_logger.warning(f"Keys missing in {file1_name}: {missing_in_1}")
            else:
                workflow_logger.info(f"All keys match between {file1_name} and {file2_name}")

            return result

        except Exception as e:
            workflow_logger.error(f"Failed to compare i18n files: {str(e)}")
            raise ValueError(f"Failed to compare i18n files: {str(e)}")



