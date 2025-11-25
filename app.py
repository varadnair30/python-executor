from flask import Flask, request, jsonify
import subprocess
import json
import tempfile
import os
import re
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def validate_script(script):
    """Validate that script contains a main() function and is safe"""
    if not script or not isinstance(script, str):
        return False, "Script must be a non-empty string"
    
    if len(script) > 100000:  # 100KB limit
        return False, "Script too large (max 100KB)"
    
    # Check if main() function exists
    if not re.search(r'def\s+main\s*\(', script):
        return False, "Script must contain a 'def main()' function"
    
    # Basic safety checks (warning only, NsJail handles actual security)
    dangerous_patterns = [
        (r'__import__\s*\(\s*[\'"]os[\'"]', 'Suspicious import pattern detected'),
        (r'eval\s*\(', 'eval() usage detected'),
        (r'exec\s*\(', 'exec() usage detected'),
    ]
    
    for pattern, warning in dangerous_patterns:
        if re.search(pattern, script):
            logger.warning(f"Potentially unsafe script: {warning}")
    
    return True, None

def execute_script_with_nsjail(script):
    """Execute Python script in NsJail sandbox with Cloud Run compatible settings"""
    
    # Create temporary file for the script
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        script_path = f.name
        # Write user script
        f.write(script)
        f.write("\n\n")
        # Append result extraction code
        f.write("if __name__ == '__main__':\n")
        f.write("    import json\n")
        f.write("    import sys\n")
        f.write("    try:\n")
        f.write("        result = main()\n")
        f.write("        print('__RESULT_START__', file=sys.stderr)\n")
        f.write("        print(json.dumps(result), file=sys.stderr)\n")
        f.write("        print('__RESULT_END__', file=sys.stderr)\n")
        f.write("    except Exception as e:\n")
        f.write("        print(f'__ERROR__:{type(e).__name__}: {str(e)}', file=sys.stderr)\n")
        f.write("        sys.exit(1)\n")
    
    try:
        # Cloud Run compatible nsjail with stronger isolation
        nsjail_cmd = [
            '/usr/local/bin/nsjail',
            '-Me',  # Execve mode
            '--user', '99999',
            '--group', '99999',
            '--time_limit', '30',
            # Resource limits (without RTPRIO)
            '--rlimit_as', '700',
            '--rlimit_cpu', '20', 
            '--rlimit_fsize', '1',
            '--rlimit_nofile', '32',
            '--rlimit_nproc', 'soft',  # Use soft limit
            '--rlimit_stack', 'soft',  # Use soft limit
            # Skip problematic rlimits
            '--disable_no_new_privs',  # May help with capabilities
            # Filesystem isolation
            '-R', '/usr/local/lib/python3.11',
            '-R', '/usr/local/bin/python3.11',
            '-R', '/lib',
            '-R', '/lib64',
            '-R', '/usr/lib',
            '--tmpfsmount', '/tmp',
            '-E', 'PATH=/usr/local/bin:/usr/bin:/bin',
            # Namespace isolation
            '--disable_clone_newnet',
            '--disable_clone_newuser',
            '--disable_clone_newns',
            '--disable_clone_newcgroup',
            '--disable_clone_newipc',
            '--disable_clone_newuts',
            '--disable_clone_newpid',
            '--quiet',
            '--',
            '/usr/local/bin/python3.11',
            script_path
        ]
        
        logger.info(f"Executing script with NsJail (Cloud Run compatible mode)")
        
        # Execute with timeout
        result = subprocess.run(
            nsjail_cmd,
            capture_output=True,
            text=True,
            timeout=35  # Slightly longer than NsJail's timeout
        )
        
        stdout = result.stdout
        stderr = result.stderr
        
        logger.info(f"Execution completed with return code: {result.returncode}")
        
        # Check for errors first
        if '__ERROR__:' in stderr:
            error_line = [line for line in stderr.split('\n') if '__ERROR__:' in line][0]
            error_msg = error_line.replace('__ERROR__:', '').strip()
            return {
                'success': False,
                'error': f'Script execution error: {error_msg}',
                'stdout': stdout.strip()
            }
        
        # Extract result from stderr (we print it there to separate from stdout)
        if '__RESULT_START__' in stderr and '__RESULT_END__' in stderr:
            start_idx = stderr.index('__RESULT_START__') + len('__RESULT_START__')
            end_idx = stderr.index('__RESULT_END__')
            result_json_str = stderr[start_idx:end_idx].strip()
            
            try:
                result_data = json.loads(result_json_str)
                logger.info("Successfully parsed result JSON")
                return {
                    'success': True,
                    'result': result_data,
                    'stdout': stdout.strip()
                }
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return {
                    'success': False,
                    'error': f'main() must return a JSON-serializable object. Parse error: {str(e)}',
                    'stdout': stdout.strip()
                }
        else:
            # No result markers found
            error_msg = "Script did not return a value or main() was not called"
            if stderr:
                error_msg += f". Error output: {stderr.strip()}"
            
            logger.warning(f"Execution failed: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'stdout': stdout.strip()
            }
    
    except subprocess.TimeoutExpired:
        logger.error("Script execution timeout")
        return {
            'success': False,
            'error': 'Script execution timeout (maximum 30 seconds)',
            'stdout': ''
        }
    except FileNotFoundError:
        logger.error("NsJail binary not found")
        return {
            'success': False,
            'error': 'Sandbox environment not available',
            'stdout': ''
        }
    except Exception as e:
        logger.error(f"Unexpected error during execution: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Internal execution error: {str(e)}',
            'stdout': ''
        }
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(script_path):
                os.unlink(script_path)
                logger.debug(f"Cleaned up temp file: {script_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file: {e}")

@app.route('/execute', methods=['POST'])
def execute():
    """Execute Python script endpoint"""
    
    logger.info("Received execution request")
    
    # Validate content type
    if not request.is_json:
        logger.warning("Invalid content type")
        return jsonify({'error': 'Content-Type must be application/json'}), 400
    
    # Parse request
    try:
        data = request.get_json()
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return jsonify({'error': 'Invalid JSON in request body'}), 400
    
    if not data or 'script' not in data:
        logger.warning("Missing 'script' field in request")
        return jsonify({'error': 'Request must contain "script" field'}), 400
    
    script = data['script']
    
    # Validate script
    is_valid, error_msg = validate_script(script)
    if not is_valid:
        logger.warning(f"Script validation failed: {error_msg}")
        return jsonify({'error': error_msg}), 400
    
    # Execute script
    execution_result = execute_script_with_nsjail(script)
    
    if execution_result['success']:
        logger.info("Script executed successfully")
        return jsonify({
            'result': execution_result['result'],
            'stdout': execution_result['stdout']
        }), 200
    else:
        logger.warning(f"Script execution failed: {execution_result['error']}")
        return jsonify({
            'error': execution_result['error'],
            'stdout': execution_result['stdout']
        }), 400

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for Cloud Run"""
    return jsonify({
        'status': 'healthy',
        'service': 'python-executor',
        'version': '1.0.0'
    }), 200

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API information"""
    return jsonify({
        'service': 'Python Code Executor',
        'version': '1.0.0',
        'endpoints': {
            '/execute': 'POST - Execute Python script',
            '/health': 'GET - Health check'
        },
        'documentation': 'See README.md for usage examples'
    }), 200

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Get port from environment (Cloud Run sets this)
    port = int(os.environ.get('PORT', 8080))
    
    # Check if NsJail is available
    try:
        subprocess.run(
            ['/usr/local/bin/nsjail', '--help'],
            capture_output=True,
            timeout=5
        )
        logger.info("NsJail is available and ready")
    except Exception as e:
        logger.error(f"NsJail not available: {e}")
    
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
