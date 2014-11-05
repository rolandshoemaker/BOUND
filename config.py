#################################
# BIND zone conf file locations #
#################################
bind_zone_confs = ['test.conf.local']

######################
# Zone style options #
######################
relativize_zones = True

###########################
# BOUND optional sections #
###########################
show_stats = True
check_bind_bin = 'bin/check_bind.sh'
check_bind_xtra = ['-V 9.5']
