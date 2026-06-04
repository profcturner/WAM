# Helper Functions used in the project

def divide_by_semesters(total_hours, semester_string):
    """divide hours equally between targeted semesters

    total_hours     the total number of hours to divide
    semester_string comma separated list of semesters the hours are in

    returns a list with the first item containing the total and
    then each following item being the hours for that semester
    """
    semesters = [s.strip() for s in semester_string.split(',')]
    no_semesters = len(semesters)
    split_hours = [
        total_hours / no_semesters if str(semester) in semesters else 0
        for semester in range(1, 4)
    ]
    split_hours.insert(0, total_hours)
    return split_hours