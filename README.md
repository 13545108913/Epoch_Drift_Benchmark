# Epoch-Drift-Benchmark

## 安装库：
```bash
pip install browsergym  # (recommended) everything below
pip install browsergym-experiments  # experiment utilities (agent, loop, benchmarks) + everything below
pip install browsergym-core  # core functionalities only (no benchmark, just the openended task)
pip install browsergym-miniwob  # core + miniwob
pip install browsergym-webarena  # core + webarena
pip install browsergym-visualwebarena  # core + visualwebarena
pip install browsergym-workarena  # core + workarena
pip install browsergym-assistantbench  # core + assistantbench
pip install weblinx-browsergym  # core + weblinx

playwright install chromium
```

## Docker容器：

### 运行 GitLab 服务

1. 启动服务
```bash
docker-compose -f docker-compose.v12.yml up -d
```

2. 查看服务状态
```bash
docker-compose -f docker-compose.v12.yml ps
```

3. 查看实时日志
```bash
docker-compose -f docker-compose.v12.yml logs -f
```

### 停止 GitLab 服务

1. 停止服务（保留数据）
```bash
docker-compose -f docker-compose.v12.yml stop
```

2. 停止并删除容器（保留数据）
```bash
docker-compose -f docker-compose.v12.yml down
```

3. 完全停止并清理所有资源
```bash
docker-compose -f docker-compose.v12.yml down --volumes
```

### 设置外部URL
```bash
docker exec gitlab-v13.0 sed -i "s|^external_url.*|external_url 'http://172.26.116.102:8080'|" /etc/gitlab/gitlab.rb
docker exec gitlab-v13.0 gitlab-ctl reconfigure
```

### 账户密码
Account: root

Password: zlxQGkIhkgLcnGpsJyMRjAGdPhKP75k2mscZZJm6b+A=



## 设置环境变量：
```bash
$env:BASE_URL="http://localhost"              
$env:WA_SHOPPING="http://localhost:7770/"
$env:WA_SHOPPING_ADMIN="http://localhost:7780/admin"
$env:WA_REDDIT="http://localhost:9999"
$env:WA_GITLAB="http://localhost:8080"
$env:WA_WIKIPEDIA="http://localhost:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
$env:WA_MAP="http://localhost:3000"
$env:WA_HOMEPAGE="http://localhost:4399"
         
$env:SHOPPING="http://localhost:7770/"
$env:SHOPPING_ADMIN="http://localhost:7780/admin"
$env:REDDIT="http://localhost:9999"
$env:GITLAB="http://localhost:8080"
$env:WIKIPEDIA="http://localhost:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
$env:MAP="http://localhost:3000"
$env:HOMEPAGE="http://localhost:4399"


$env:WA_GITLAB_V1="http://localhost:8080"
$env:WA_GITLAB_V2="http://localhost:8080"
```

```bash
ASE_URL="http://localhost"                                                                                     
export WA_SHOPPING="$BASE_URL:7770/"
export WA_SHOPPING_ADMIN="$BASE_URL:7780/admin"
export WA_REDDIT="$BASE_URL:9999"
export WA_GITLAB="$BASE_URL:8023"
export WA_WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export WA_MAP="$BASE_URL:3000"
export WA_HOMEPAGE="$BASE_URL:4399"

export SHOPPING="$BASE_URL:7770/"
export SHOPPING_ADMIN="$BASE_URL:7780/admin"
export REDDIT="$BASE_URL:9999"
export GITLAB="$BASE_URL:8023"
export WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export MAP="$BASE_URL:3000"
export HOMEPAGE="$BASE_URL:4399"

export WA_GITLAB_V1="$BASE_URL:8023"
export WA_GITLAB_V2="$BASE_URL:8023"
```

## 运行方式
```bash
python run_demo.py --task_name myBenchmark.419
python run_online.py --experiment asi --website gitlab --task_ids 419-419
```