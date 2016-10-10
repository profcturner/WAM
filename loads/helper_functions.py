def divide_by_semesters(total_hours, semester_string):
    """divide hours equally between targeted semesters
    
    total_hours     the total number of hours to divide
    semester_string comma separated list of semesters
    
    returns a list with hours in each of three semesters
    followed by the total itself
    """
    semesters = semester_string.split(',')
    
    # Create a list to contain their subdivision
    split_hours = list()
    # How many semesters are listed?
    no_semesters = len(semesters)
    # We currently have three semesters, 1, 2 and 3
    for s in range(1,4):
        # Check if this one is flagged, brutally ugly code :-(
        # TODO: Try and fix the abomination 
        if semester_string.count(str(s)) > 0:
            split_hours.append(total_hours / no_semesters)
        else:
            # Nothing in this semester
            split_hours.append(0)
    
    split_hours.append(total_hours)        
    return split_hours
    