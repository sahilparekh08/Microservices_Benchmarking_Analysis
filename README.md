# Microservices Benchmarking and Analysis

Use Jaeger tracing and profiling on CPUs with Intel CAT technology. This repository can be used to benchmark microservices where request traces can be collected using a jaeger agent.

### Prerequisites

Uses Intel CAT technology to allocate cache partitions to cores. Use isolcpus to isolate a core to run the microservice to be profiled on and another core to run the profiling code.

### Instructions

This is currently only configured to run microservice graphs from the [DeathStarBench](https://github.com/delimitrou/DeathStarBench) suite.

Example command:
./scripts/run_benchmark_analysis  
    --container-name "socialnetwork-user-timeline-service-1"           # Container from the deathstarbench socialnetwork graph to profile
    --service-name-for-traces "user-timeline-service"                  # Service name for services that run on the above container as configured for jaeger
    --test-name "Compose Post"                                         # Test name
    --config "t6 c6 d30 R6 cp2"                                        # Config: t = number of threads, c = number of clients, d = duration of test, R = requests per second, cp = number of cache partitions attached to the core on which the target microservice is pinned
    --docker-compose-dir "~/workspace/DeathStarBench/socialNetwork"    # path to the docker-compose.yml file
    --core-to-pin-profiler 6                                           # core on which the profiling code will run
    --cores-to-profile 7                                               # core to profile (llc loads, llc misses, instructions retired)
    --cos 0,1,3                                                        # CoS in consideration (Intel CAT)
    --jaeger-traces-limit 1000                                         # (optional arg) number requests to collect jaeger traces for
    --save-traces-json                                                 # (optional arg) this saves the jaeger trace jsons
    --non-idle-duration-only-mode                                      # (optional arg) when supplied, the cores are not profiled but only request non idle execution times are collected
    --num-runs 10                                                      # (optional arg) how many times to run the test
