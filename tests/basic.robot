*** Settings ***
Library       pyats.robot.pyATSRobot
Library       unicon.robot.UniconRobot
Library       genie.libs.robot.GenieRobot
Library       Collections
Variables     testvars.yaml

Suite Setup   setup

*** Variables ***

*** Test Cases ***

Check Version
    FOR  ${dev}   IN   @{devices_under_test}
        ${result}=  parse "show version" on device "${dev}"
        # no real useful test here, just for demo
        Log Dictionary   ${result}
        Should be equal  ${result}[version][os]    IOS-XE
    END

Check ACL
    FOR  ${dev}   IN   @{devices_under_test}
        ${result}=  parse "show access-list" on device "${dev}"
        Log Dictionary   ${result}
        Dictionary should contain Key   ${result}   SNMP   msg=ACL 'SNMP' not found
        Dictionary should contain Key   ${result}   SSH   msg=ACL 'SSH' not found
    END

*** Keywords ***
setup
    # '[ WARN ] Could not load the Datafile correctly' can be ignored
    use genie testbed "${CURDIR}/testbed.yaml"
    FOR  ${dev}   IN   @{devices_under_test}
        connect to device "${dev}"
    END