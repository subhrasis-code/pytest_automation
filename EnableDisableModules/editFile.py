import re
import copy

def edit_file_in_local(local_file_path, moduleToEnable, list_of_modules, emailConfig):
    moduleToEnable_temp = copy.copy(moduleToEnable)



    print(f"\nModule/Modules need to be enabled ----> {moduleToEnable_temp}\n")
    with open(local_file_path, 'r') as isv_file:
        isv_file_lines = []
        for line in isv_file:
            isv_file_lines.append(line)

        # Edit file logic started
        print("    Initiated Enabling and Disabling of modules in    \n")
        while len(moduleToEnable_temp) > 0:
            pop_module = moduleToEnable_temp.pop()
            list_of_modules.remove(pop_module)
            # Reset the file pointer to the beginning of the file
            isv_file.seek(0)
            for i in range(len(isv_file_lines)):
                if pop_module in isv_file_lines[i]:
                    if '>0<' in isv_file_lines[i]:
                        isv_file_lines[i] = isv_file_lines[i].replace('>0<', '>1<')

        while len(list_of_modules) > 0:
            pop_module = list_of_modules.pop()
            # Reset the file pointer to the beginning of the file
            isv_file.seek(0)
            for i in range(len(isv_file_lines)):
                if pop_module in isv_file_lines[i]:
                    if '>1<' in isv_file_lines[i]:
                        isv_file_lines[i] = isv_file_lines[i].replace('>1<', '>0<')
        print("    Completed Enabling and Disabling of modules    \n")


        # Editing the Email configurations
        # Reset the file pointer to the beginning of the file
        print("    Initiated Editing the Email configurations    \n")
        isv_file.seek(0)
        # iterate through emailConfig dictionary
        for key, value in emailConfig.items():
            # print(key, value)
            for i in range(len(isv_file_lines)):
                if key in isv_file_lines[i]:
                    splitLine = isv_file_lines[i].split(">") # eg: ['    <smtpserverip', '127.0.0.1</smtpserverip', '\n']
                    oldValue = splitLine[1].split("<")[0] # eg: 127.0.0.1
                    isv_file_lines[i] = isv_file_lines[i].replace(oldValue, str(value))
        print("    Completed Editing the Email configurations    \n")


    with open(local_file_path, 'w') as isv_file:
        isv_file.writelines(isv_file_lines)
    print("Successfully edited {}.".format(local_file_path))