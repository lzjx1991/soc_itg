# 用法: source /home/server/soc_itg/env.sh
SOC_ITG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SOC_ITG_ROOT
export PYTHONPATH="$SOC_ITG_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$SOC_ITG_ROOT/bin:$PATH"
echo "soc-itg env ready: $SOC_ITG_ROOT (python: $SOC_ITG_ROOT/.venv/bin/python)"
