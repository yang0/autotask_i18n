try:
    from autotask.nodes import Node, GeneratorNode, ConditionalNode, register_node
except ImportError:
    from stub import Node, GeneratorNode, ConditionalNode, register_node

from typing import Dict, Any, Generator, List
import os
import re


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

    def execute(self, node_inputs: Dict[str, Any], workflow_logger) -> Dict[str, Any]:
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
