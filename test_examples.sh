#!/bin/bash

# Test script for the Python Executor API
# Usage: ./test_examples.sh [URL]
# Default URL: http://localhost:8080

URL="${1:-http://localhost:8080}"

echo "🧪 Testing Python Executor API at: $URL"
echo "================================================"
echo ""

# Test 1: Simple Hello World
echo "Test 1: Simple Hello World"
echo "---"
curl -s -X POST "$URL/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "script": "def main():\n    return {\"message\": \"Hello, World!\"}"
  }' | python3 -m json.tool
echo ""
echo ""

# Test 2: With stdout
echo "Test 2: Script with stdout"
echo "---"
curl -s -X POST "$URL/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "script": "def main():\n    print(\"Processing...\")\n    result = 2 + 2\n    print(f\"Result is: {result}\")\n    return {\"answer\": result}"
  }' | python3 -m json.tool
echo ""
echo ""

# Test 3: Using pandas
echo "Test 3: Using pandas"
echo "---"
curl -s -X POST "$URL/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "script": "import pandas as pd\n\ndef main():\n    df = pd.DataFrame({\"a\": [1, 2, 3], \"b\": [4, 5, 6]})\n    return {\"sum_a\": int(df[\"a\"].sum()), \"sum_b\": int(df[\"b\"].sum()), \"rows\": len(df)}"
  }' | python3 -m json.tool
echo ""
echo ""

# Test 4: Using numpy
echo "Test 4: Using numpy"
echo "---"
curl -s -X POST "$URL/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "script": "import numpy as np\n\ndef main():\n    arr = np.array([1, 2, 3, 4, 5])\n    return {\"mean\": float(arr.mean()), \"std\": float(arr.std()), \"sum\": int(arr.sum())}"
  }' | python3 -m json.tool
echo ""
echo ""

# Test 5: Using os module
echo "Test 5: Using os module"
echo "---"
curl -s -X POST "$URL/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "script": "import os\n\ndef main():\n    return {\"platform\": os.name, \"cpu_count\": os.cpu_count()}"
  }' | python3 -m json.tool
echo ""
echo ""

# Test 6: Error - No main function
echo "Test 6: Error - No main() function"
echo "---"
curl -s -X POST "$URL/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "script": "def calculate():\n    return {\"value\": 42}"
  }' | python3 -m json.tool
echo ""
echo ""

# Test 7: Error - main() doesn't return JSON
echo "Test 7: Error - main() doesn't return JSON"
echo "---"
curl -s -X POST "$URL/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "script": "def main():\n    return \"not a json object\""
  }' | python3 -m json.tool
echo ""
echo ""

# Test 8: Complex computation
echo "Test 8: Complex computation"
echo "---"
curl -s -X POST "$URL/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "script": "import pandas as pd\nimport numpy as np\n\ndef main():\n    data = {\"x\": np.random.rand(100), \"y\": np.random.rand(100)}\n    df = pd.DataFrame(data)\n    return {\n        \"mean_x\": float(df[\"x\"].mean()),\n        \"mean_y\": float(df[\"y\"].mean()),\n        \"correlation\": float(df[\"x\"].corr(df[\"y\"]))\n    }"
  }' | python3 -m json.tool
echo ""
echo ""

echo "================================================"
echo "✅ All tests completed!"