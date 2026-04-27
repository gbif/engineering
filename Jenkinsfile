pipeline {
  agent any

  triggers {
    cron('H 5 * * *')
  }

  options {
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '30'))
    disableConcurrentBuilds()
  }

  parameters {
    choice(name: 'MODE', choices: ['both', 'github', 'admin'], description: 'Which monitoring checks to run')
    string(name: 'GITHUB_OWNER', defaultValue: 'gbif', description: 'GitHub owner/org for config source repo')
    string(name: 'GITHUB_REPO', defaultValue: 'gbif-configuration', description: 'GitHub repository for config source')
    string(name: 'GITHUB_REF', defaultValue: 'master', description: 'Git ref/branch/tag for config source')
    string(name: 'ENVS', defaultValue: 'dev,test,prod,lab', description: 'Comma-separated environments to validate')
    string(name: 'ADMIN_URL', defaultValue: 'http://ws.gbif.org', description: 'WS admin URL for /instances check')
    string(name: 'POLICY_FILE', defaultValue: 'scripts/policy.json', description: 'Local policy file path')
    string(name: 'GITHUB_TOKEN_CREDENTIALS_ID', defaultValue: '', description: 'Optional Jenkins Secret Text credentials ID for GITHUB_TOKEN')
  }

  environment {
    PYTHONUNBUFFERED = '1'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Setup Python') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
chmod +x scripts/run-monitoring-checks.sh
'''
      }
    }

    stage('Run Monitoring Checks') {
      steps {
        script {
          def runCmd = '''#!/usr/bin/env bash
set -euo pipefail
. .venv/bin/activate
scripts/run-monitoring-checks.sh \
  --mode "$MODE" \
  --github-owner "$GITHUB_OWNER" \
  --github-repo "$GITHUB_REPO" \
  --github-ref "$GITHUB_REF" \
  --envs "$ENVS" \
  --admin-url "$ADMIN_URL" \
  --policy-file "$POLICY_FILE"
'''

          if (params.MODE == 'github' || params.MODE == 'both') {
            if (params.GITHUB_TOKEN_CREDENTIALS_ID?.trim()) {
              withCredentials([string(credentialsId: params.GITHUB_TOKEN_CREDENTIALS_ID.trim(), variable: 'GITHUB_TOKEN')]) {
                sh runCmd
              }
            } else {
              echo 'GITHUB_TOKEN_CREDENTIALS_ID is empty; using existing GITHUB_TOKEN environment variable if present.'
              sh runCmd
            }
          } else {
            sh runCmd
          }
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'reports/monitoring/**', allowEmptyArchive: true
    }
  }
}

