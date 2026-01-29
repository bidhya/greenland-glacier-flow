#!usr/bin/env python


###################################################################################################
# Imports.
###################################################################################################

import sys, logging


###################################################################################################
# Functions.
###################################################################################################

def traceback_to_string(tb):
    output_strings = []
    local_vars = {}
    while tb:
        filename = tb.tb_frame.f_code.co_filename
        name = tb.tb_frame.f_code.co_name
        line_no = tb.tb_lineno
        output_strings.append(f"File {filename} line {line_no}, in {name}")
        local_vars = tb.tb_frame.f_locals
        if not hasattr(tb, 'next'):
            break
        tb = tb.next
    output_strings.append(f"Local variables in top frame: {local_vars}")
    return "\n".join(output_strings)


def setUpBasicLoggingConfig(log_name, starting_message):
    # If there's not already a logger configured for a higher-level script,
    if not logging.getLogger().hasHandlers():
        # Set up logging for unhandled exceptions.
        def unhandled_exception_hook(type, value, tb):
            message = f'{type}\n{value}\n{traceback_to_string(tb)}'
            logging.error(f'Unhandled exception: {message}')
        sys.excepthook = unhandled_exception_hook

        # Set up basic logging configuration.
        logging.basicConfig(
            filename=f'{log_name}', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s'
        )

    # Do basic intro logging for the current script.
    log_to_stdout_and_file("\n\n-----------------------BEGIN-----------------------\n")
    log_to_stdout_and_file(starting_message)


def log_to_stdout_and_file(message):
    logging.info(message)
    print(message)