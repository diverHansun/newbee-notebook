param(
    [Parameter(Mandatory = $true)]
    [string]$Id,
    [switch]$Yes
)

$args = @("-m", "newbee_notebook.scripts.clean_document", "--id", $Id)
if ($Yes) {
    $args += "--yes"
}

python @args

