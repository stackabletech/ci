module.exports = {
    repositories: [
      'stackabletech/hdfs-operator'
      // 'stackabletech/kafka-operator',
      // 'stackabletech/airflow-operator',
      // 'stackabletech/superset-operator',
      // 'stackabletech/nifi-operator',
      // 'stackabletech/hive-operator',
      // 'stackabletech/hbase-operator',
      // 'stackabletech/spark-k8s-operator',
      // 'stackabletech/secret-operator',
      // 'stackabletech/hdfs-operator',
      // 'stackabletech/listener-operator',
      // 'stackabletech/commons-operator',
      // 'stackabletech/opa-operator',
      // 'stackabletech/trino-operator',
      // 'stackabletech/docker-images',
      // 'stackabletech/operator-rs',
      // 'stackabletech/operator-templating',
      // 'stackabletech/operator-rs',
      // 'stackabletech/operator-rs'
    ],
    gitAuthor: "Stacky McStackface <serviceaccounts@stackable.de>",
    includeForks: true,
    logFileLevel: 'debug',
    logLevel: 'debug',
    force: {
      schedule: [],
      prCreation: "immediate",
    }
  };