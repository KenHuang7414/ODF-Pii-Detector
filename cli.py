import sys
import argparse
from dotenv import load_dotenv
load_dotenv()

from src.pipeline import run

def main():
    parser = argparse.ArgumentParser(description="ODT PII Detector")
    parser.add_argument("input", help="輸入 .odt 路徑")
    parser.add_argument("--strategy", choices=["block", "label", "partial"], default="block")
    parser.add_argument("--no-llm", action="store_true", help="只跑正則，不呼叫 Claude")
    args = parser.parse_args()
    
    result = run(
        input_path=args.input,
        strategy=args.strategy,
        use_llm=not args.no_llm,
    )
    print("\n完成！")
    print(f"  遮蔽版：{result['masked']}")
    print(f"  報告：  {result['report']}")
    print(f"  總計：  {result['total_matches']} 筆 PII")

if __name__ == "__main__":
    main()