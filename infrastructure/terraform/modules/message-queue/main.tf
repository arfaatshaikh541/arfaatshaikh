# Message-queue module: Amazon MSK (managed Kafka), the KAFKA_BROKERS
# backing apps/worker's internal/consumer/kafka_adapter.go (segmentio/kafka-go).

resource "aws_security_group" "msk" {
  name_prefix = "${var.name_prefix}-msk-"
  description = "Allows Kafka broker traffic only from the security groups explicitly passed in."
  vpc_id      = var.vpc_id

  ingress {
    description     = "Kafka plaintext"
    from_port       = 9092
    to_port         = 9092
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  ingress {
    description     = "Kafka TLS"
    from_port       = 9094
    to_port         = 9094
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-msk-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_cloudwatch_log_group" "msk_broker_logs" {
  name              = "/gridkeep/${var.name_prefix}/msk"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

resource "aws_msk_cluster" "this" {
  cluster_name           = "${var.name_prefix}-msk"
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.number_of_broker_nodes

  broker_node_group_info {
    instance_type   = var.broker_instance_type
    client_subnets  = var.subnet_ids
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = var.broker_ebs_volume_size_gb
      }
    }
  }

  encryption_info {
    encryption_in_transit {
      # apps/worker's kafka-go client (internal/consumer/kafka_adapter.go)
      # does not currently configure a TLS Dialer or SASL credentials --
      # TLS_PLAINTEXT keeps both the plaintext listener (what the worker
      # uses today) and the TLS listener (for future/other clients)
      # available on the same cluster, rather than silently breaking the
      # worker or overstating a TLS guarantee the application doesn't
      # actually enforce yet. Tightening this to "TLS" only, together with
      # adding a TLS Dialer to KafkaReader/KafkaDeadLetterWriter, is tracked
      # as follow-up application work, not done in this milestone.
      client_broker = "TLS_PLAINTEXT"
      in_cluster    = true
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk_broker_logs.name
      }
    }
  }

  enhanced_monitoring = "PER_TOPIC_PER_BROKER"

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-msk"
  })
}
