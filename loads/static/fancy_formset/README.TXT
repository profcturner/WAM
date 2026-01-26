WARNING!

This file is here because there is an apparent bug in fancy_formset 1.0.0, which seems to decrement total forms on
a form deletion. This does not appear to be correct behaviour, and can be diagnosed from trying to delete a single
remaining formset that was already in the model layer.

This file includes a patched version of the library that will be loaded in preference if STATICFILES_DIR is set
up correctly.

This file / directory needs to be removed if and when the library is patched, or this local copy will continue to
override the main library.