# Microservices Benchmarking and Analysis

Use Jaeger tracing and profiling on CPUs with Intel CAT technology. This repository can be used to benchmark microservices where request traces can be collected using a jaeger agent.

### Prerequisites

Uses Intel CAT technology to allocate cache partitions to cores. Use isolcpus to isolate a core to run the microservice to be profiled on and another core to run the profiling code.

### Instructions

This is currently only configured to run microservice graphs from the [DeathStarBench](https://github.com/delimitrou/DeathStarBench) suite.

Example command:
```
./scripts/run_benchmark_analysis \
  # Container from the DeathStarBench socialnetwork graph to profile
  --container-name "socialnetwork-user-timeline-service-1" \
  # Service name as configured in Jaeger for the container
  --service-name-for-traces "user-timeline-service" \
  # Name of the test
  --test-name "Compose Post" \
  # Configuration:
  #   t  = number of threads
  #   c  = number of clients
  #   d  = duration of test (in seconds)
  #   R  = requests per second
  #   cp = number of cache partitions attached to the core
  --config "t6 c6 d30 R6 cp2" \
  # Path to the docker-compose.yml file
  --docker-compose-dir "~/workspace/DeathStarBench/socialNetwork" \
  # Core on which the profiling code will run
  --core-to-pin-profiler 6 \
  # Core to profile (LLC loads, LLC misses, instructions retired)
  --cores-to-profile 7 \
  # Classes of Service (Intel CAT)
  --cos 0,1,3 \
  # (Optional) Number of requests to collect Jaeger traces for
  --jaeger-traces-limit 1000 \
  # (Optional) Save the Jaeger trace JSONs
  --save-traces-json \
  # (Optional) Only collect request non-idle execution times (no core profiling)
  --non-idle-duration-only-mode \
  # (Optional) Number of times to run the test
  --num-runs 10
```
